import streamlit as st
import yt_dlp
import os
import tempfile
import shutil
import re

def is_valid_url(url):
    # Simple URL validation
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    return url_pattern.match(url) is not None

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
        except yt_dlp.utils.DownloadError as e:
            st.error(f"Error fetching video information: {str(e)}")
            return [], None
        except Exception as e:
            st.error(f"An unexpected error occurred: {str(e)}")
            return [], None

# ... [rest of the functions remain the same] ...

st.title("Video Downloader")

url = st.text_input("Enter the video URL:")

if url:
    if not is_valid_url(url):
        st.warning("Please enter a valid URL.")
    else:
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
            st.error(f"An unexpected error occurred: {str(e)}")
else:
    st.info("Please enter a valid URL to start.")
