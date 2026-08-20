import streamlit as st
import requests
from urllib.parse import unquote, urlparse
import re
import os
import shutil
import zipfile
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

@st.cache_data
def create_extension_zip():
    """Creates a zip file of the extension folder for download."""
    extension_dir = os.path.join(os.path.dirname(__file__), 'extension')
    
    if not os.path.exists(extension_dir):
        return None
    
    # Create zip in memory
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(extension_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(extension_dir))
                zip_file.write(file_path, arcname)
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

# Hero Section
st.markdown("""
    <h1 style='text-align: center; color: #6f42c1; margin-bottom: 0.5rem;'>
        📥 GDrive Video
    </h1>
    <p style='text-align: center; color: #666; font-size: 1.2rem; margin-bottom: 2rem;'>
        Download a video you already have permission to access and save.
    </p>
""", unsafe_allow_html=True)

# Feature highlights
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("✅", "Authorized Use", "Your Access")
with col2:
    st.metric("⌨️", "Safe Resume", "CLI Only")
with col3:
    st.metric("⚡", "Fast & Efficient", "Optimized Speed")
with col4:
    st.metric("💾", "Easy Download", "One Click")

# Main content area
st.divider()

st.warning("""
**Legacy preview/install surface:** this page buffers a download in server memory
and does not use the Milestone D integrity/resume core. Use the local CLI for
private, large, interrupted, or integrity-sensitive transfers. Never upload a
cookie export to a hosted Streamlit instance.
""")

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
    test_button = st.button("📥 Download Video", use_container_width=True, type="primary")

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
                            - The file is not accessible to this public legacy tester
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

# Get extension zip
extension_zip = create_extension_zip()

with col1:
    if extension_zip:
        st.download_button(
            label="⬇️ Download Extension",
            data=extension_zip,
            file_name="gdrive-video-extension.zip",
            mime="application/zip",
            use_container_width=True,
            help="Download the extension folder as ZIP"
        )
    else:
        st.markdown("""
            <button style='width: 100%; padding: 0.75rem; background-color: #666; color: white; border: none; border-radius: 0.25rem; cursor: not-allowed;'>
                ⬇️ Download Extension
            </button>
        """, unsafe_allow_html=True)
        st.caption("❌ Extension folder not found")

st.markdown("""
#### 📖 How to Install Manually:

**Option 1: Using Downloaded ZIP (Easiest)**
1. Click "⬇️ Download Extension" button above
2. Extract the ZIP file to a folder
3. Open `chrome://extensions/` (or `edge://extensions/`)
4. Enable **Developer mode** (toggle in top-right corner)
5. Click **Load unpacked** 
6. Select the extracted `extension` folder
7. Done! The extension appears in your toolbar

**Option 2: Clone from GitHub**
1. Visit [GitHub Repository](https://github.com/juansilvadesign/gdrive-video)
2. Clone or download the repo
3. Open `chrome://extensions/`
4. Enable **Developer mode**
5. Click **Load unpacked** and select the `extension` folder
6. Done!

**Using the Extension:**
- Navigate to any Google Drive video
- Click the extension icon in your toolbar
- Click **ON** to enable URL capturing
- Watch the video load, then click download!
""")

# Features Section
st.divider()
st.markdown("### ✨ Features")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    **✅ Authorized Use**
    - Files you own or have permission to save
    - Existing Google Drive access only
    - No access-control or legal-rights determination
    
    **🔄 Safe CLI Transfers**
    - Verified resume and atomic final files
    - Credential-safe status output
    - The CLI, not this page, provides these guarantees
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
