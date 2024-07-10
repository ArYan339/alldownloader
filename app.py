import streamlit as st
import yt_dlp
import os
import tempfile
import shutil

def get_available_formats(url):
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            formats = info['formats']
            video_formats = [f for f in formats if f.get('vcodec', 'none') != 'none']
            video_formats.sort(key=lambda f: (f.get('height', 0), f.get('fps', 0)), reverse=True)
            
            unique_resolutions = []
            seen_resolutions = set()
            for f in video_formats:
                resolution = f'{f.get("height", 0)}p'
                fps = f.get('fps', 0)
                key = (resolution, fps)
                if key not in seen_resolutions:
                    seen_resolutions.add(key)
                    unique_resolutions.append((f['format_id'], f'{resolution} - {fps}fps - {f["ext"]}'))
            
            unique_resolutions.append(('bestaudio/best', 'Audio Only (MP3)'))
            return unique_resolutions, info['title']
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
                filename = ydl.prepare_filename(info)
                
                # If it's an audio download, change the extension to mp3
                if format_id == 'bestaudio/best':
                    filename = os.path.splitext(filename)[0] + '.mp3'
            
            if os.path.exists(filename):
                sanitized_filename = sanitize_filename(os.path.basename(filename))
                new_filename = os.path.join(temp_dir, sanitized_filename)
                shutil.move(filename, new_filename)
                
                # Read the file content
                with open(new_filename, "rb") as file:
                    file_content = file.read()
                
                return sanitized_filename, file_content
            else:
                raise Exception(f"Downloaded file not found: {filename}")
        except Exception as e:
            raise Exception(f"Error during download: {str(e)}")

st.title("Video Downloader")

url = st.text_input("Enter the video URL:")

if url:
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
                    
                    # Create a download button
                    st.download_button(
                        label="Click here to download",
                        data=file_content,
                        file_name=filename,
                        mime="application/octet-stream"
                    )
                except Exception as e:
                    st.error(f"An error occurred during download: {str(e)}")
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
else:
    st.info("Please enter a valid URL to start.")
