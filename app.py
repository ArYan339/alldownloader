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
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    return url_pattern.match(url) is not None

def get_random_user_agent():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15'
    ]
    return random.choice(user_agents)

def get_ydl_opts():
    return {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'user_agent': get_random_user_agent(),
        'format': 'best[height<=360]',  # Limit to 360p
        'socket_timeout': 30,
        'retry_sleep_functions': {'429': lambda _: 60},
    }

def get_available_formats(url, max_retries=5, retry_delay=10):
    for attempt in range(max_retries):
        try:
            ydl_opts = get_ydl_opts()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info is None:
                    raise Exception("Unable to extract video information.")
                
                formats = info.get('formats', [])
                if not formats:
                    raise Exception("No formats found.")
                
                # Filter formats to only include videos up to 360p and audio
                video_formats = [f for f in formats if f.get('vcodec', 'none') != 'none' 
                               and f.get('height', 0) <= 360]
                audio_formats = [f for f in formats if f.get('acodec', 'none') != 'none' 
                               and f.get('vcodec', 'none') == 'none']
                
                if not video_formats and not audio_formats:
                    raise Exception("No suitable formats found.")
                
                unique_formats = []
                seen_resolutions = set()
                
                # Add video formats up to 360p
                for f in video_formats:
                    height = f.get('height', 0)
                    if height <= 360:
                        resolution = f'{height}p'
                        if resolution not in seen_resolutions:
                            seen_resolutions.add(resolution)
                            unique_formats.append((f['format_id'], f'{resolution} - {f["ext"]}'))
                
                # Add audio option
                if audio_formats:
                    unique_formats.append(('bestaudio/best', 'Audio Only (MP3)'))
                
                return unique_formats, info.get('title', 'Untitled')
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            raise

def sanitize_filename(filename):
    return "".join([c for c in filename if c.isalpha() or c.isdigit() or c in ' .-_']).rstrip()

def update_progress(d, progress_bar, progress_text):
    if d['status'] == 'downloading':
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        downloaded_bytes = d.get('downloaded_bytes', 0)
        if total_bytes > 0:
            progress = downloaded_bytes / total_bytes
            progress_bar.progress(progress)
            progress_text.text(f"Downloaded: {downloaded_bytes/1024/1024:.1f}MB / {total_bytes/1024/1024:.1f}MB")
    elif d['status'] == 'finished':
        progress_bar.progress(1.0)
        progress_text.text("Download completed. Processing...")

def download_video(url, format_id, progress_bar, progress_text, max_retries=5, retry_delay=10):
    with tempfile.TemporaryDirectory() as temp_dir:
        for attempt in range(max_retries):
            try:
                ydl_opts = get_ydl_opts()
                ydl_opts.update({
                    'format': format_id if format_id != 'bestaudio/best' else 'bestaudio/best',
                    'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                    'progress_hooks': [lambda d: update_progress(d, progress_bar, progress_text)],
                })
                
                if format_id == 'bestaudio/best':
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
                    
                    if format_id == 'bestaudio/best':
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
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise

st.title("YouTube Video Downloader (360p)")

url = st.text_input("Enter the YouTube video URL:")

if url:
    if not is_valid_url(url):
        st.warning("Please enter a valid URL.")
    else:
        st.write(f"Attempting to fetch video information for URL: {url}")
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
    st.info("Please enter a valid YouTube URL to start.")
