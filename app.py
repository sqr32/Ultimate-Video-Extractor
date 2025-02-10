from flask import Flask, render_template, request, jsonify
from flask_bootstrap import Bootstrap
import yt_dlp
from urllib.parse import urlparse
import json
from video_cdn_extractor import extract_cdn_info
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
Bootstrap(app)

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def handle_extraction_error(error):
    error_message = str(error)
    error_mappings = {
        "Sign in to confirm your age": "هذا الفيديو مقيد بالعمر. جاري محاولة تجاوز القيود...",
        "Private video": "هذا فيديو خاص ولا يمكن الوصول إليه",
        "This video is unavailable": "هذا الفيديو غير متاح",
        "Video unavailable": "الفيديو غير متوفر. قد يكون محذوفاً أو خاصاً",
        "Unable to extract video data": "تعذر استخراج بيانات الفيديو. يرجى التحقق من الرابط",
        "Incomplete YouTube ID": "رابط YouTube غير صحيح",
        "HTTP Error 429": "تم تجاوز حد الطلبات. يرجى المحاولة بعد قليل",
        "This live event will begin in": "هذا بث مباشر لم يبدأ بعد",
        "Join this channel to get access": "هذا المحتوى متاح فقط لأعضاء القناة",
        "Content is not available": "المحتوى غير متاح في منطقتك"
    }
    
    for key, value in error_mappings.items():
        if key in error_message:
            return {"error": value}
    
    return {"error": f"حدث خطأ: {error_message}"}

def extract_video_info(url):
    if not is_valid_url(url):
        return {"error": "Invalid URL format"}

    try:
        base_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'format': 'bestvideo[ext=mp4][protocol!*=dash][protocol!*=m3u8]+bestaudio[ext=m4a]/best[ext=mp4][protocol!*=dash][protocol!*=m3u8]/best[protocol!*=dash][protocol!*=m3u8]',
            'cookiefile': 'cookies.txt',
            'no_check_certificates': True,
            'ignoreerrors': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Sec-Fetch-Dest': 'document',
                'DNT': '1',
                'Upgrade-Insecure-Requests': '1'
            },
            'socket_timeout': 30,
            'retries': 5,
            'age_limit': None,
            'prefer_insecure': True,
            'allow_unplayable_formats': False,
            'hls_prefer_native': False,
            'prefer_ffmpeg': True,
            'youtube_include_dash_manifest': False,
            'youtube_include_hls_manifest': False,
            'extractor_args': {
                'youtube': {
                    'skip': ['dash', 'hls'],
                    'player_skip': ['js', 'configs', 'webpage']
                }
            },
            'geo_bypass': True,
            'geo_bypass_country': 'US'
        }

        def try_extract_with_options(ydl_options):
            try:
                with yt_dlp.YoutubeDL(ydl_options) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info:
                        # Get direct video URLs
                        if 'formats' in info:
                            # Filter and sort formats
                            formats = [f for f in info['formats'] if 
                                     f.get('url') and 
                                     f.get('protocol', '').lower() not in ['m3u8', 'm3u8_native', 'dash', 'dash_manifest'] and
                                     not any(x in str(f.get('format_note', '')).lower() 
                                         for x in ['audio only', 'images', 'thumbnail'])]
                            
                            # Sort by quality
                            formats.sort(key=lambda x: (
                                float(x.get('tbr', 0) or 0),
                                x.get('height', 0) or 0,
                                x.get('width', 0) or 0,
                                x.get('fps', 0) or 0,
                                x.get('ext', '') == 'mp4'  # Prefer MP4
                            ), reverse=True)
                            
                            # Update format URLs to ensure they're direct
                            for fmt in formats:
                                if fmt.get('url'):
                                    fmt['url'] = fmt['url'].split('?')[0] + '?' + '&'.join([
                                        param for param in fmt['url'].split('?')[1].split('&')
                                        if not param.startswith(('range=', 'rn=', 'rbuf=', 'mime='))
                                    ]) if '?' in fmt['url'] else fmt['url']
                            
                            return info, formats
                    return info, []
            except Exception as e:
                return None, []

        # Try different format combinations
        for format_option in [
            'bestvideo[ext=mp4][protocol!*=dash][protocol!*=m3u8]+bestaudio[ext=m4a]/best[ext=mp4][protocol!*=dash][protocol!*=m3u8]',
            'best[ext=mp4][protocol!*=dash][protocol!*=m3u8]',
            'best[protocol!*=dash][protocol!*=m3u8]'
        ]:
            ydl_opts = base_opts.copy()
            ydl_opts['format'] = format_option
            info, formats = try_extract_with_options(ydl_opts)
            
            if info and formats:
                video_data = {
                    'title': info.get('title', 'Unknown'),
                    'thumbnail': info.get('thumbnail', ''),
                    'description': info.get('description', ''),
                    'duration': info.get('duration', 0),
                    'view_count': info.get('view_count', 0),
                    'platform': info.get('extractor', 'Unknown'),
                    'watch_url': info.get('webpage_url', url),
                    'formats': [],
                    'uploader': info.get('uploader', 'Unknown'),
                    'upload_date': info.get('upload_date', ''),
                    'like_count': info.get('like_count', 0),
                    'channel_url': info.get('channel_url', ''),
                    'channel_follower_count': info.get('channel_follower_count', 0)
                }

                # Add formats with direct URLs
                for fmt in formats:
                    if fmt.get('protocol', '').lower() not in ['m3u8', 'm3u8_native', 'dash', 'dash_manifest']:
                        format_info = {
                            'quality': f"{fmt.get('height', 0)}p" if fmt.get('height') else 'auto',
                            'format': fmt.get('ext', 'mp4'),
                            'resolution': f"{fmt.get('width', 'N/A')}x{fmt.get('height', 'N/A')}",
                            'filesize': fmt.get('filesize', 0),
                            'url': fmt['url'],
                            'vcodec': fmt.get('vcodec', 'unknown'),
                            'acodec': fmt.get('acodec', 'unknown'),
                            'fps': fmt.get('fps', 'N/A'),
                            'tbr': fmt.get('tbr', 0)
                        }
                        video_data['formats'].append(format_info)

                if video_data['formats']:
                    default_format = video_data['formats'][0]
                    video_data.update({
                        'quality': default_format['quality'],
                        'resolution': default_format['resolution'],
                        'format': default_format['format'],
                        'download_url': default_format['url']
                    })

                return video_data

        return {"error": "لم نتمكن من استخراج معلومات الفيديو. قد يكون الفيديو خاص أو مقيد."}

    except Exception as e:
        return handle_extraction_error(e)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract():
    url = request.form.get('url')
    if not url:
        return jsonify({"error": "No URL provided"})
    
    video_info = extract_video_info(url)
    return jsonify(video_info)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 