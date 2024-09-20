import streamlit as st
import yt_dlp
import os
import tempfile
import shutil
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def is_valid_url(url):
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    return url_pattern.match(url) is not None

def get_video_info(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(5)  # Additional wait to ensure page is fully loaded
        
        title = driver.title
        page_source = driver.page_source
        
        return title, page_source
    finally:
        driver.quit()

def get_available_formats(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
    }
    
    try:
        title, page_source = get_video_info(url)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if info is None:
                raise Exception("Unable to extract video information.")
            
            formats = info.get('formats', [])
            if not formats:
                raise Exception("No formats found.")
            
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
            
            return unique_formats, title
    except Exception as e:
        st.error(f"Error fetching video information: {str(e)}")
        return [], None

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

def download_video(url, format_id, progress_bar, progress_text):
    with tempfile.TemporaryDirectory() as temp_dir:
        ydl_opts = {
            'format': f'{format_id}+bestaudio/best' if format_id != 'bestaudio/best' else 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'progress_hooks': [lambda d: update_progress(d, progress_bar, progress_text)],
        }
        
        if format_id == 'bestaudio/best':
            ydl_opts.update({
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        
        try:
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
            st.error(f"Error during download: {str(e)}")
            raise

st.title("Video Downloader")

url = st.text_input("Enter the video URL:")

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
    st.info("Please enter a valid URL to start.")
