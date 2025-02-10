import yt_dlp
from urllib.parse import urlparse
import sys
import random
import logging
import browser_cookie3
import tempfile
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_browser_cookies():
    """
    Get cookies from installed browsers with better error handling and logging
    """
    cookies = []
    browsers = [
        (browser_cookie3.chrome, "Chrome"),
        (browser_cookie3.firefox, "Firefox"),
        (browser_cookie3.edge, "Edge")
    ]
    
    for browser_func, browser_name in browsers:
        try:
            # Get YouTube cookies
            browser_cookies = browser_func(domain_name=".youtube.com")
            if browser_cookies:
                logger.info(f"Found {len(list(browser_cookies))} YouTube cookies in {browser_name}")
                for cookie in browser_cookies:
                    logger.info(f"Cookie: {cookie.name} from {cookie.domain}")
                    cookies.append(cookie)

            # Get googlevideo.com cookies
            video_cookies = browser_func(domain_name=".googlevideo.com")
            if video_cookies:
                logger.info(f"Found {len(list(video_cookies))} googlevideo cookies in {browser_name}")
                for cookie in video_cookies:
                    logger.info(f"Cookie: {cookie.name} from {cookie.domain}")
                    cookies.append(cookie)

            # Get google.com cookies
            google_cookies = browser_func(domain_name=".google.com")
            if google_cookies:
                logger.info(f"Found {len(list(google_cookies))} Google cookies in {browser_name}")
                for cookie in google_cookies:
                    logger.info(f"Cookie: {cookie.name} from {cookie.domain}")
                    cookies.append(cookie)

        except Exception as e:
            logger.warning(f"Could not get cookies from {browser_name}: {str(e)}")
            continue
    
    return cookies

def save_browser_cookies():
    """
    Save browser cookies to a temporary file with better formatting
    """
    cookies = get_browser_cookies()
    if not cookies:
        logger.warning("No browser cookies found")
        return None
        
    cookie_file = os.path.join(tempfile.gettempdir(), "youtube_cookies.txt")
    try:
        with open(cookie_file, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n")
            f.write("# This is a generated file!  Do not edit.\n\n")
            
            for cookie in cookies:
                if cookie.domain in [".youtube.com", ".googlevideo.com", ".google.com"]:
                    # Format: domain\tdom_spec\tpath\tsecure\texpiry\tname\tvalue
                    f.write(f"{cookie.domain}\t"  # domain
                           f"{'TRUE' if cookie.domain.startswith('.') else 'FALSE'}\t"  # include subdomains
                           f"{cookie.path}\t"  # path
                           f"{'TRUE' if cookie.secure else 'FALSE'}\t"  # secure
                           f"{int(cookie.expires) if cookie.expires else 0}\t"  # expiry
                           f"{cookie.name}\t"  # name
                           f"{cookie.value}\n")  # value
                           
        logger.info(f"Saved {len(cookies)} cookies to {cookie_file}")
        return cookie_file
    except Exception as e:
        logger.error(f"Error saving cookies: {str(e)}")
        return None

def extract_cdn_info(url):
    """
    Extract CDN information from videos on a webpage
    Returns a dictionary containing the CDN URL and other info
    """
    if not is_valid_url(url):
        logger.error(f"Invalid URL format: {url}")
        return {"error": "رابط غير صالح"}

    # Try to get browser cookies first
    cookie_file = save_browser_cookies()
    if cookie_file:
        logger.info(f"Using browser cookies from {cookie_file}")
        # Verify cookie file contents
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookie_content = f.read()
                logger.info(f"Cookie file contents: {cookie_content[:500]}...")  # Log first 500 chars
        except Exception as e:
            logger.error(f"Error reading cookie file: {str(e)}")
    else:
        logger.warning("Using default cookies")
        cookie_file = 'cookies.txt'

    # Updated headers with more modern values
    base_headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Origin': 'https://www.youtube.com',
        'Referer': 'https://www.youtube.com/',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'Sec-Fetch-Dest': 'video',
        'Range': 'bytes=0-',
        'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'DNT': '1',
        'Connection': 'keep-alive'
    }

    # Check if it's a direct googlevideo.com URL
    if 'googlevideo.com' in url:
        try:
            # Create a video data structure for direct URLs
            video_data = {
                'title': 'Direct Video',
                'thumbnail': '',
                'description': '',
                'duration': 0,
                'view_count': 0,
                'platform': 'googlevideo',
                'watch_url': url,
                'formats': [{
                    'quality': 'direct',
                    'format': 'mp4',
                    'resolution': 'original',
                    'filesize': 0,
                    'url': url,
                    'vcodec': 'unknown',
                    'acodec': 'unknown',
                    'fps': 'N/A',
                    'tbr': 0
                }],
                'download_url': url
            }
            return video_data
        except Exception as e:
            logger.error(f"Error processing direct URL: {str(e)}")
            return {"error": "تعذر معالجة الرابط المباشر"}

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'extract_flat': False,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'no_check_certificates': True,
        'prefer_insecure': True,
        'cookiefile': cookie_file,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'referer': 'https://www.youtube.com/',
        'http_headers': base_headers,
        'socket_timeout': 30,
        'retries': 15,
        'fragment_retries': 10,
        'retry_sleep': lambda n: 5 * (n + 1),
        'age_limit': None,
        'prefer_ffmpeg': True,
        'hls_prefer_native': False,
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        'nocheckcertificate': True,
        'source_address': '0.0.0.0',
        'extractor_args': {
            'youtube': {
                'skip': ['dash', 'hls'],
                'player_skip': ['js', 'configs', 'webpage']
            }
        }
    }

    # Add random IP addresses for X-Forwarded-For
    ip_addresses = [
        f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
        for _ in range(5)
    ]

    # Updated list of user agents
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
    ]
    
    # Add proxy support with more options
    proxies = [
        None,  # Try without proxy first
        'socks5://127.0.0.1:9050',  # Tor proxy if available
        'http://127.0.0.1:8080',    # Local proxy if available
        'https://127.0.0.1:8080'    # HTTPS proxy if available
    ]

    for proxy in proxies:
        if proxy:
            ydl_opts['proxy'] = proxy
            
        for user_agent in user_agents:
            for ip in ip_addresses:
                try:
                    ydl_opts['user_agent'] = user_agent
                    ydl_opts['http_headers'].update({
                        'User-Agent': user_agent,
                        'X-Forwarded-For': ip,
                        'Client-IP': ip
                    })
                    
                    logger.info(f"Attempting to extract info for URL: {url}")
                    logger.info(f"Using User-Agent: {user_agent}")
                    logger.info(f"Using IP: {ip}")
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        try:
                            info = ydl.extract_info(url, download=False)
                            
                            if not info:
                                logger.error("No information extracted")
                                continue
                            
                            # Get direct video URLs
                            if 'formats' in info:
                                formats = []
                                for f in info['formats']:
                                    if not f.get('url'):
                                        continue
                                    
                                    # Skip HLS and DASH formats
                                    if f.get('protocol', '').lower() in ['m3u8', 'm3u8_native', 'dash', 'dash_manifest']:
                                        continue
                                        
                                    # Skip audio-only formats
                                    if any(x in str(f.get('format_note', '')).lower() for x in ['audio only', 'images', 'thumbnail']):
                                        continue
                                        
                                    # Add format to list
                                    formats.append(f)
                                
                                if not formats:
                                    logger.error("No suitable formats found")
                                    continue
                                
                                # Sort formats by quality
                                formats.sort(key=lambda x: (
                                    float(x.get('tbr', 0) or 0),
                                    x.get('height', 0) or 0,
                                    x.get('width', 0) or 0,
                                    x.get('fps', 0) or 0,
                                    x.get('ext', '') == 'mp4'
                                ), reverse=True)
                                
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
                                
                                # Process each format
                                for fmt in formats:
                                    try:
                                        video_url = fmt['url']
                                        if '?' in video_url:
                                            base_url = video_url.split('?')[0]
                                            params = [
                                                param for param in video_url.split('?')[1].split('&')
                                                if not param.startswith(('range=', 'rn=', 'rbuf=', 'mime='))
                                            ]
                                            video_url = f"{base_url}?{'&'.join(params)}" if params else base_url
                                        
                                        format_info = {
                                            'quality': f"{fmt.get('height', 0)}p" if fmt.get('height') else 'auto',
                                            'format': fmt.get('ext', 'mp4'),
                                            'resolution': f"{fmt.get('width', 'N/A')}x{fmt.get('height', 'N/A')}",
                                            'filesize': fmt.get('filesize', 0),
                                            'url': video_url,
                                            'vcodec': fmt.get('vcodec', 'unknown'),
                                            'acodec': fmt.get('acodec', 'unknown'),
                                            'fps': fmt.get('fps', 'N/A'),
                                            'tbr': fmt.get('tbr', 0)
                                        }
                                        video_data['formats'].append(format_info)
                                    except Exception as e:
                                        logger.warning(f"Error processing format: {e}")
                                        continue
                                
                                if video_data['formats']:
                                    default_format = video_data['formats'][0]
                                    video_data.update({
                                        'quality': default_format['quality'],
                                        'resolution': default_format['resolution'],
                                        'format': default_format['format'],
                                        'download_url': default_format['url']
                                    })
                                    logger.info("Successfully extracted video information")
                                    
                                    # Clean up temporary cookie file
                                    if cookie_file != 'cookies.txt':
                                        try:
                                            os.remove(cookie_file)
                                        except:
                                            pass
                                        
                                    return video_data
                                
                                logger.error("No valid formats found after processing")
                                continue
                            
                            logger.error("No formats found in extracted info")
                            continue
                            
                        except yt_dlp.utils.DownloadError as e:
                            error_message = str(e)
                            if "Sign in to confirm you're not a bot" in error_message:
                                logger.warning(f"Bot detection encountered with User-Agent: {user_agent}")
                                continue
                            elif "HTTP Error 403" in error_message:
                                logger.warning(f"Access denied (403) with User-Agent: {user_agent}")
                                continue
                            logger.error(f"yt-dlp download error: {error_message}")
                            continue
                        except Exception as e:
                            logger.error(f"Error during info extraction: {str(e)}")
                            continue
                            
                except Exception as e:
                    logger.error(f"Unexpected error with User-Agent {user_agent}: {str(e)}")
                    continue
            
    # Clean up temporary cookie file
    if cookie_file != 'cookies.txt':
        try:
            os.remove(cookie_file)
        except:
            pass
    
    return {"error": "تعذر استخراج معلومات الفيديو. يرجى المحاولة مرة أخرى لاحقاً"}

def print_highest_quality(info):
    """
    Print highest quality format information
    """
    if 'formats' in info:
        # Filter and sort video formats
        formats = sorted(
            [f for f in info['formats'] if 
             f.get('url') is not None and
             not any(x in str(f.get('format_note', '')).lower() for x in ['audio', 'images', 'thumbnail'])
            ],
            key=lambda x: (
                float(x.get('tbr', 0) or 0),  # Bitrate
                x.get('height', 0) or 0,      # Height
                x.get('width', 0) or 0,       # Width
                x.get('fps', 0) or 0          # FPS
            ),
            reverse=True
        )
        
        if formats:
            best_format = formats[0]
            print(f"Title: {info.get('title', 'Unknown')}")
            print(f"Platform: {info.get('extractor', 'Unknown')}")
            print(f"Quality: {best_format.get('format_note', 'N/A')}")
            print(f"Resolution: {best_format.get('resolution', 'N/A')}")
            print(f"Bitrate: {best_format.get('tbr', 'N/A')} kbps")
            print(f"FPS: {best_format.get('fps', 'N/A')}")
            print(f"Format: {best_format.get('ext', 'N/A')}")
            print(f"CDN URL: {best_format.get('url', 'N/A')}")
            print("-" * 50)
        else:
            # Try alternative format extraction
            if 'url' in info:
                print(f"Title: {info.get('title', 'Unknown')}")
                print(f"Platform: {info.get('extractor', 'Unknown')}")
                print(f"Direct URL: {info['url']}")
                print("-" * 50)
            else:
                print("No video formats found.")
    else:
        print("No CDN information found for this video.")

def main():
    print("Universal Video CDN Extractor")
    print("=" * 50)
    print("Supported Platforms:")
    print("- YouTube")
    print("- Vimeo")
    print("- Dailymotion")
    print("- Facebook")
    print("- Twitter")
    print("- Instagram")
    print("- TikTok")
    print("- And many more video platforms")
    print("\nSupports:")
    print("- Single videos")
    print("- Playlists")
    print("- Channels")
    print("- User profiles")
    print("- Watch pages")
    
    while True:
        url = input("\nEnter URL (or 'q' to quit): ")
        
        if url.lower() == 'q':
            break
            
        extract_cdn_info(url)

if __name__ == "__main__":
    main() 