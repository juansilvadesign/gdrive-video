import streamlit as st
import requests
from urllib.parse import unquote, urlparse
import re
import os
from io import BytesIO

# Page configuration
st.set_page_config(
    page_title="GDrive Video - Download Google Drive Videos",
    page_icon="📥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
    <style>
    /* Main theme */
    :root {
        --primary-color: #6f42c1;
        --secondary-color: #5a32a3;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Custom styling */
    .main {
        max-width: 1000px;
    }
    
    .hero-title {
        text-align: center;
        margin: 2rem 0;
        color: #1f1f1f;
    }
    
    .hero-subtitle {
        text-align: center;
        color: #666;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1.5rem;
        margin: 2rem 0;
    }
    
    .feature-card {
        padding: 1.5rem;
        border-radius: 0.5rem;
        background-color: #f5f5f5;
        border-left: 4px solid #6f42c1;
    }
    
    .feature-card h3 {
        color: #6f42c1;
        margin-top: 0;
    }
    
    .extension-buttons {
        display: flex;
        gap: 1rem;
        flex-wrap: wrap;
        justify-content: center;
        margin: 2rem 0;
    }
    
    .stButton > button {
        width: 100%;
        padding: 0.75rem;
    }
    </style>
""", unsafe_allow_html=True)

# Extract video ID helper function
def extract_video_id(url_or_id: str) -> str:
    """Extracts video ID from Google Drive URL or returns the ID if already provided."""
    if '/' not in url_or_id and '.' not in url_or_id:
        return url_or_id
    
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'/open\?id=([a-zA-Z0-9_-]+)',
        r'/view\?id=([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    
    id_match = re.search(r'([a-zA-Z0-9_-]{25,50})', url_or_id)
    if id_match:
        return id_match.group(1)
    
    return url_or_id

def validate_video_id(video_id: str) -> bool:
    """Validates if the video ID looks like a valid Google Drive ID."""
    return bool(re.match(r'^[a-zA-Z0-9_-]{25,50}$', video_id))

def get_video_url(page_content: str) -> tuple:
    """Extracts the video playback URL and title from the page content."""
    contentList = page_content.split("&")
    video, title = None, None
    for content in contentList:
        if content.startswith('title=') and not title:
            title = unquote(content.split('=')[-1])
        elif "videoplayback" in content and not video:
            video = unquote(content).split("|")[-1]
        if video and title:
            break
    return video, title

def sanitize_filename(filename: str) -> str:
    """Sanitizes the filename by removing invalid characters."""
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = "".join(char for char in filename if ord(char) >= 32)
    return filename.strip()

# Hero Section
st.markdown("""
    <h1 style='text-align: center; color: #6f42c1; margin-bottom: 0.5rem;'>
        📥 GDrive Video
    </h1>
    <p style='text-align: center; color: #666; font-size: 1.2rem; margin-bottom: 2rem;'>
        Download videos from Google Drive, even view-only files!
    </p>
""", unsafe_allow_html=True)

# Feature highlights
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🔓", "View-Only Access", "Bypass Restrictions")
with col2:
    st.metric("🔄", "Resume Downloads", "Continue Interrupted")
with col3:
    st.metric("⚡", "Fast & Efficient", "Optimized Speed")
with col4:
    st.metric("💾", "Easy Download", "One Click")

# Main content area
st.divider()

# Live Tester Section
st.markdown("### 🎯 Test It Live")
st.markdown("Paste a Google Drive video URL or ID below and download your video:")

# Input section
col1, col2 = st.columns([3, 1])
with col1:
    video_input = st.text_input(
        "Google Drive Video URL or ID",
        placeholder="https://drive.google.com/file/d/VIDEO_ID/view or just the VIDEO_ID",
        label_visibility="collapsed"
    )
with col2:
    test_button = st.button("🔍 Test", use_container_width=True, type="primary")

# Test and download logic
if test_button and video_input:
    video_id = extract_video_id(video_input)
    
    if not validate_video_id(video_id):
        st.error("❌ Invalid video ID. Please check your URL and try again.")
    else:
        try:
            with st.spinner("🔍 Retrieving video information..."):
                drive_url = f'https://drive.google.com/u/0/get_video_info?docid={video_id}&drive_originator_app=303'
                response = requests.get(drive_url, timeout=10)
                
                if response.status_code != 200:
                    st.error(f"❌ Failed to access Google Drive (Status: {response.status_code})")
                else:
                    video_url, title = get_video_url(response.text)
                    
                    if not video_url:
                        st.error("""
                            ❌ Unable to retrieve the video URL.
                            
                            Possible reasons:
                            - Video ID is incorrect
                            - Video is private or restricted
                            - Video has been deleted
                            - Network connectivity issues
                        """)
                    else:
                        st.success("✅ Video found!")
                        
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.markdown(f"**📹 Video Title:** {title}")
                            st.markdown(f"**🔗 Video ID:** `{video_id}`")
                        
                        # Try to get file size
                        try:
                            head_response = requests.head(video_url, timeout=10)
                            file_size = int(head_response.headers.get('content-length', 0))
                            size_mb = file_size / (1024 * 1024)
                            st.markdown(f"**📊 File Size:** {size_mb:.1f} MB")
                        except:
                            pass
                        
                        st.divider()
                        
                        # Download button
                        try:
                            with st.spinner("⬇️ Downloading video..."):
                                video_response = requests.get(video_url, timeout=30, cookies=response.cookies)
                                
                                if video_response.status_code == 200:
                                    filename = sanitize_filename(title) + ".mp4"
                                    st.download_button(
                                        label=f"💾 Download {filename}",
                                        data=video_response.content,
                                        file_name=filename,
                                        mime="video/mp4",
                                        use_container_width=True
                                    )
                                    st.success("✅ Ready to download!")
                                else:
                                    st.error("❌ Failed to download video. Please try again.")
                        except Exception as e:
                            st.error(f"❌ Download error: {str(e)}")
        
        except requests.exceptions.Timeout:
            st.error("❌ Request timed out. Please check your internet connection.")
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")

# Divider
st.divider()

# Extension Installation Section
st.markdown("### 🚀 Install the Chrome Extension")
st.markdown("""
The GDrive Video Extension lets you download videos directly from Google Drive with one click!
Works on Chrome, Edge, Brave, and other Chromium-based browsers.
""")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
        <a href="https://chrome.google.com/webstore/search/gdrive%20video" target="_blank">
            <button style='width: 100%; padding: 0.75rem; background-color: #4285F4; color: white; border: none; border-radius: 0.25rem; cursor: pointer; font-weight: bold;'>
                + Add to Chrome
            </button>
        </a>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
        <a href="https://microsoftedge.microsoft.com/addons/search/gdrive%20video" target="_blank">
            <button style='width: 100%; padding: 0.75rem; background-color: #0078D4; color: white; border: none; border-radius: 0.25rem; cursor: pointer; font-weight: bold;'>
                + Add to Edge
            </button>
        </a>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
        <a href="https://github.com/juansilvadesign/gdrive-video/tree/main/extension" target="_blank">
            <button style='width: 100%; padding: 0.75rem; background-color: #333; color: white; border: none; border-radius: 0.25rem; cursor: pointer; font-weight: bold;'>
                📦 Load from GitHub
            </button>
        </a>
    """, unsafe_allow_html=True)

st.markdown("""
#### 📖 How to Install Manually:
1. Clone or download the repository from [GitHub](https://github.com/juansilvadesign/gdrive-video)
2. Open `chrome://extensions/` (or `edge://extensions/`)
3. Enable **Developer mode** (top-right corner)
4. Click **Load unpacked** and select the `extension` folder
5. Done! The extension will appear in your toolbar
""")

# Features Section
st.divider()
st.markdown("### ✨ Features")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    **🔓 Access Control Bypass**
    - Download view-only videos
    - Bypass Google Drive restrictions
    - Access protected content
    
    **🔄 Smart Downloads**
    - Resumable downloads
    - Real-time progress tracking
    - Custom chunk sizes
    """)

with col2:
    st.markdown("""
    **⚙️ Customization**
    - Custom output naming
    - Configurable parameters
    - Verbose logging mode
    
    **📊 User Experience**
    - Interactive interface
    - Detailed status info
    - Easy to use
    """)

# Footer
st.divider()
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.markdown("""
    <div style='text-align: center; color: #999; font-size: 0.9rem;'>
        <p>Made with 💜 by <strong><a href='https://github.com/juansilvadesign' target='_blank'>Juan Silva</a></strong></p>
        <p>
            <a href='https://github.com/juansilvadesign/gdrive-video' target='_blank'>GitHub</a> • 
            <a href='https://github.com/juansilvadesign/gdrive-video/issues' target='_blank'>Report Issues</a> • 
            <a href='https://github.com/juansilvadesign/gdrive-video/blob/main/LICENSE' target='_blank'>MIT License</a>
        </p>
    </div>
    """, unsafe_allow_html=True)
