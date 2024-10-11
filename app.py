import streamlit as st
import os
import tempfile
import shutil
import re
import random
import subprocess
import sys
import time
import requests
from urllib.parse import parse_qs, urlparse

def install_latest_yt_dlp():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"])

try:
    import yt_dlp
except ImportError:
    install_latest_yt_dlp()
    import yt_dlp

def is_valid_url(url):
    # Updated pattern to support both YouTube and Instagram URLs
    url_pattern = re.compile(
        r'(?:https?://)?(?:www\.)?'
        r'(?:(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)|'
        r'(?:instagram\.com/(?:p/|reel/|tv/)))'
        r'[\w\-_]+'
    )
    return bool(url_pattern.match(url))

def is_instagram_url(url):
    return 'instagram.com' in url.lower()

def get_random_user_agent():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1'
    ]
    return random.choice(user_agents)

def get_ydl_opts(is_instagram=False):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'user_agent': get_random_user_agent(),
        'socket_timeout': 30,
        'retry_sleep_functions': {'429': lambda _: 60},
        'extract_flat': 'in_playlist',
    }
    
    if is_instagram:
        # Special options for Instagram
        opts.update({
            'format': 'best',  # Instagram usually provides a single format
            'add_header': [
                ('User-Agent', get_random_user_agent()),
                ('Cookie', ''),  # Add your Instagram cookies here if needed
            ],
            'extractor_args': {
                'instagram': {
                    'compatible_un': [''],  # Add Instagram username if needed
                }
            }
        })
    else:
        # YouTube specific options
        opts.update({
            'extractor_args': {'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['dash', 'hls'],
            }}
        })
    
    return opts

def get_available_formats(url, max_retries=5, retry_delay=10):
    is_instagram = is_instagram_url(url)
    
    for attempt in range(max_retries):
        try:
            ydl_opts = get_ydl_opts(is_instagram)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info is None:
                    raise Exception("Unable to extract video information.")
                
                formats = info.get('formats', [])
                if not formats:
                    raise Exception("No formats found.")
                
                if is_instagram:
                    # Instagram typically provides a single best format
                    return [('best', 'Best Quality')], info.get('title', 'Instagram Video')
                else:
                    # YouTube format handling
                    video_formats = [f for f in formats if f.get('vcodec', 'none') != 'none']
                    audio_formats = [f for f in formats if f.get('acodec', 'none') != 'none']
                    
                    if not video_formats and not audio_formats:
                        raise Exception("No suitable formats found.")
                    
                    unique_formats = []
                    
                    if video_formats:
                        video_formats.sort(key=lambda f: (f.get('height', 0), f.get('fps', 0)), reverse=True)
                        seen_resolutions = set()
                        for f in video_formats:
                            resolution = f'{f.get("height", 0)}p'
                            fps = f.get('fps', 0)
                            key = (resolution, fps)
                            if key not in seen_resolutions:
                                seen_resolutions.add(key)
                                unique_formats.append((f['format_id'], f'{resolution} - {fps}fps - {f["ext"]}'))
                    
                    if audio_formats:
                        unique_formats.append(('bestaudio/best', 'Audio Only (MP3)'))
                    
                    return unique_formats, info.get('title', 'Untitled')
                    
        except yt_dlp.utils.DownloadError as e:
            if "Sign in to confirm you're not a bot" in str(e):
                st.error("Sign-in required. Please try a different video URL.")
                return [], None
            elif "Private video" in str(e):
                st.error("This video is private or requires authentication.")
                return [], None
            else:
                st.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    st.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    st.error(f"Error fetching video information after {max_retries} attempts.")
                    return [], None

def download_video(url, format_id, progress_bar, progress_text, max_retries=5, retry_delay=10):
    is_instagram = is_instagram_url(url)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for attempt in range(max_retries):
            try:
                ydl_opts = get_ydl_opts(is_instagram)
                ydl_opts.update({
                    'format': format_id,
                    'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                    'progress_hooks': [lambda d: update_progress(d, progress_bar, progress_text)],
                })
                
                if not is_instagram and format_id == 'bestaudio/best':
                    ydl_opts.update({
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                    })
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if info is None:
                        raise Exception("Unable to download video")
                    filename = ydl.prepare_filename(info)
                    
                    if not is_instagram and format_id == 'bestaudio/best':
                        filename = os.path.splitext(filename)[0] + '.mp3'
                
                if os.path.exists(filename):
                    sanitized_filename = sanitize_filename(os.path.basename(filename))
                    new_filename = os.path.join(temp_dir, sanitized_filename)
                    shutil.move(filename, new_filename)
                    
                    with open(new_filename, "rb") as file:
                        file_content = file.read()
                    
                    return sanitized_filename, file_content
                else:
                    raise Exception(f"Downloaded file not found: {filename}")
            except Exception as e:
                st.warning(f"Download attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    st.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    st.error(f"Error during download after {max_retries} attempts.")
                    raise

# Rest of the code remains the same (sanitize_filename and update_progress functions)

st.title("YouTube & Instagram Video Downloader")

url = st.text_input("Enter the YouTube or Instagram video URL:")

if url:
    if not is_valid_url(url):
        st.warning("Please enter a valid YouTube or Instagram URL.")
    else:
        platform = "Instagram" if is_instagram_url(url) else "YouTube"
        st.write(f"Attempting to fetch {platform} video information...")
        try:
            formats, video_title = get_available_formats(url)
            if not formats:
                st.warning("No suitable formats found. Please check the URL and try again.")
            else:
                st.success(f"Video found: {video_title}")
                format_dict = dict(formats)
                selected_format = st.selectbox("Choose format:", [f[1] for f in formats])
                selected_format_id = [k for k, v in format_dict.items() if v == selected_format][0]

                if st.button("Download"):
                    progress_bar = st.progress(0)
                    progress_text = st.empty()
                    try:
                        filename, file_content = download_video(url, selected_format_id, progress_bar, progress_text)
                        st.success("Download completed!")
                        
                        st.download_button(
                            label="Click here to download",
                            data=file_content,
                            file_name=filename,
                            mime="application/octet-stream"
                        )
                    except Exception as e:
                        st.error(f"An error occurred during download: {str(e)}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
else:
    st.info("Please enter a valid YouTube or Instagram URL to start.")
