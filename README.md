<div align="center">
  <img src="images/logo.png" alt="GDrive Video Logo" width="128" height="128">

  # 📥 GDrive Video 💾

  [![Python](https://img.shields.io/badge/Python-3.7%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
  [![Requests](https://img.shields.io/badge/Requests-HTTP%20Library-green?style=for-the-badge&logo=python&logoColor=white)](https://pypi.org/project/requests/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](https://opensource.org/licenses/MIT)
  [![Google Drive](https://img.shields.io/badge/Google%20Drive-Compatible-4285F4?style=for-the-badge&logo=googledrive&logoColor=white)](https://drive.google.com)

  ![GitHub stars](https://img.shields.io/github/stars/juansilvadesign/gdrive-video?style=social)
  ![GitHub forks](https://img.shields.io/github/forks/juansilvadesign/gdrive-video?style=social)
  ![GitHub issues](https://img.shields.io/github/issues/juansilvadesign/gdrive-video?style=social)

  *A powerful Python tool to download videos from Google Drive, even view-only files!* 🎯

</div>

---

## 📋 Overview

**GDrive Video** is a robust Python-based tool that enables effortless downloading of videos from Google Drive, **including those marked as _view-only_** (without download buttons). It features resumable downloads, real-time progress tracking, and extensive customization options for seamless video acquisition.

## ✨ Features

<table>
<tr>
<td>

### 🔓 Access Control Bypass
- Download **view-only** videos (no download button required)
- Bypass Google Drive restrictions
- Access protected content

</td>
<td>

### 🔄 Smart Downloads
- **Resumable downloads** (continue from interruption)
- Real-time progress tracking
- Custom chunk sizes for optimization

</td>
</tr>
<tr>
<td>

### ⚙️ Customization
- Custom output file naming
- Configurable download parameters
- Verbose logging mode

</td>
<td>

### 📊 User Experience
- Interactive progress bars
- Detailed status information
- Command-line interface

</td>
</tr>
</table>

### 🔥 Key Highlights
- 🚀 **View-Only Support**: Download restricted Google Drive videos
- 📁 **Resume Downloads**: Never lose progress on interrupted downloads
- 🎯 **High Performance**: Optimized downloading with custom chunk sizes
- 💾 **Flexible Output**: Custom naming and location options
- 🔧 **Developer Friendly**: Verbose mode for detailed execution logs

## 🚀 Quick Start

### Prerequisites
![Python](https://img.shields.io/badge/python-v3.7+-blue.svg)
![Platform](https://img.shields.io/badge/platform-windows%20%7C%20macOS%20%7C%20linux-lightgrey.svg)

### Installation Steps

> **Virtual environment required**: `run.bat` only uses the local `.env` environment and never falls back to system Python packages.

#### 1️⃣ Clone the Repository
```powershell
git clone https://github.com/juansilvadesign/gdrive-video.git
cd gdrive-video
```


#### 2️⃣ Set Up Virtual Environment
```powershell
# Create virtual environment
py -m venv .env
```

#### 3️⃣ Install Dependencies
```powershell
.env\Scripts\python.exe -m pip install -r requirements.txt
```

#### 4️⃣ Launch Application
```powershell
run.bat
```

#### 5️⃣ Done
No activation or deactivation is required when using `run.bat`.

### 🎯 One-Line Installation
```powershell
git clone https://github.com/juansilvadesign/gdrive-video.git && cd gdrive-video && py -m venv .env && .env\Scripts\python.exe -m pip install -r requirements.txt && run.bat
```

## 📦 Dependencies

### Core Libraries
| Package | Purpose | Badge |
|---------|---------|-------|
| Requests | HTTP requests for Google Drive API | ![Requests](https://img.shields.io/pypi/v/requests?label=Requests&color=green) |
| TQDM | Progress bars | ![TQDM](https://img.shields.io/pypi/v/tqdm?label=TQDM&color=blue) |
| Argparse | Command-line interface | ![Python](https://img.shields.io/badge/Built--in-Python-blue) |

## 🎯 How to Use

### Step-by-Step Guide

<table>
<tr>
<td align="center"><strong>1️⃣</strong></td>
<td><strong>Get Video ID</strong><br/>Extract the video ID from your Google Drive URL</td>
</tr>
<tr>
<td align="center"><strong>2️⃣</strong></td>
<td><strong>Run Command</strong><br/>Execute the script with the video ID as parameter</td>
</tr>
<tr>
<td align="center"><strong>3️⃣</strong></td>
<td><strong>Monitor Progress</strong><br/>Watch the real-time download progress bar</td>
</tr>
<tr>
<td align="center"><strong>4️⃣</strong></td>
<td><strong>Enjoy!</strong><br/>Your video will be saved to your specified location</td>
</tr>
</table>

### Basic Command

To download a video by its Google Drive ID:

```bash
run.bat <video_id>
```

### 📝 Getting the Video ID
From a Google Drive URL like: `https://drive.google.com/file/d/1BxBiUQN123abc456def789/view?usp=sharing`
The video ID is: `1BxBiUQN123abc456def789`

### 🛠️ Command Options

| Parameter | Short | Description | Default Value | Icon |
|-----------|-------|-------------|---------------|------|
| `<video_id>` | - | **Required**: Google Drive video ID | N/A | 🆔 |
| `--output` | `-o` | Custom output filename | Video name from GDrive | 📁 |
| `--chunk_size` | `-c` | Download chunk size (bytes) | 1024 bytes | ⚡ |
| `--verbose` | `-v` | Enable detailed logging | Disabled | 📝 |
| `--version` | - | Show script version | N/A | ℹ️ |
| `--help` | `-h` | Display help message | N/A | ❓ |

### 💡 Usage Examples

```bash
# Basic download
run.bat 1BxBiUQN123abc456def789

# Custom output filename
run.bat 1BxBiUQN123abc456def789 -o "my_video.mp4"

# Larger chunk size for faster download
run.bat 1BxBiUQN123abc456def789 -c 8192

# Verbose mode for debugging
run.bat 1BxBiUQN123abc456def789 -v

# Combined options
run.bat 1BxBiUQN123abc456def789 -o "important_video.mp4" -c 4096 -v
```

### Private links shared with one Chrome profile

The Python downloader does not run inside Chrome, so it cannot automatically "choose" a Chrome profile. For a Drive file that is only shared with one Google account, run the request with cookies exported from the Chrome profile that can open the link.

1. Open the link in the Chrome profile that has access.
2. Export cookies for Google/Drive from that profile in Netscape `cookies.txt` format. A raw `Cookie:` header saved to a text file also works.
3. Run:

```powershell
run.bat "https://drive.google.com/file/d/VIDEO_ID/view" --cookies-file "C:\path\to\cookies.txt"
```

Or use the Windows helper:

```powershell
run_with_chrome_cookies.bat
```

If that Chrome profile is signed into multiple Google accounts, try `--account-index 1`, `--account-index 2`, and so on. This maps to the number in Drive URLs like `https://drive.google.com/u/1/...`.

Keep exported cookie files private. They can act like a temporary login session, and this repo ignores common cookie filenames by default.

### How to export `cookies.txt`

Use the Chrome profile that can already open the Google Drive video. The profile matters more than the browser window: check the Chrome profile avatar in the top-right corner before exporting.

#### Option 1: Export Netscape `cookies.txt`

1. Open the Drive video link in the Chrome profile/account that has access.
2. Install [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm?hl=en) from the Chrome Web Store.
3. Open Cookie-Editor on the Drive tab and export cookies in **Netscape** format.
4. Export cookies for `google.com` or `drive.google.com`. If the exporter gives a choice, prefer `google.com` so parent-domain Google session cookies are included.
5. Save the file as something like `cookies.txt` or `my-drive.cookies.txt`.
6. Run:

```powershell
run.bat "https://drive.google.com/file/d/VIDEO_ID/view" --cookies-file ".\cookies.txt"
```

#### Option 2: Save a raw `Cookie:` header

If you do not want to use a cookie export extension, Chrome DevTools can provide the request cookie header.

1. Open the Drive video link in the Chrome profile/account that has access.
2. Press `F12` to open DevTools.
3. Go to the **Network** tab.
4. Refresh the Drive page.
5. Select a `drive.google.com` request, preferably one containing `get_video_info`.
6. In **Headers** > **Request Headers**, copy the full `Cookie:` header value.
7. Paste it into a text file, for example `cookie_header.txt`.
8. Run:

```powershell
run.bat "https://drive.google.com/file/d/VIDEO_ID/view" --cookies-file ".\cookie_header.txt"
```

The text file may contain either the whole line:

```text
Cookie: SID=...; HSID=...; SSID=...
```

or just the cookie pairs:

```text
SID=...; HSID=...; SSID=...
```

Cookie files expire. If a previously working file stops working, open the video in Chrome again and export a fresh file.

## 🗺️ Roadmap

### 🚀 Upcoming Features
- [ ] 📥 **Batch Downloads**: Process multiple video IDs from file/list
- [ ] 🎬 **Quality Selection**: Choose video resolution/quality
- [ ] 📝 **Subtitle Support**: Download video subtitles automatically
- [ ] 🏷️ **Metadata Extraction**: Get video title, description, duration
- [ ] 📱 **GUI Interface**: User-friendly graphical interface

### 🎨 User Experience Improvements
- [ ] ⚡ **Interrupt Handling**: Graceful KeyboardInterrupt management
- [ ] 🎯 **Smart Error Messages**: Context-aware error reporting
- [ ] 🔄 **Auto-Resume**: Intelligent resume on connection failure
- [ ] 📊 **Enhanced Progress**: ETA and speed indicators

### ⚡ Performance Enhancements
- [ ] 🚀 **Parallel Downloads**: Multi-threaded downloading
- [ ] 💾 **Memory Optimization**: Efficient memory usage for large files
- [ ] 🗜️ **Compression Support**: Handle compressed video formats

### 🏗️ Code Organization
- [ ] 📦 **Modular Structure**: Split into `downloader.py`, `cli.py`, `utils.py`
- [ ] 📋 **Logging System**: Professional logging with `logging` module
- [ ] ✅ **File Validation**: OS-compatible filename validation
- [ ] 🧪 **Unit Tests**: Comprehensive test coverage
- [ ] 📚 **Documentation**: API docs with `Sphinx`

---

## 🌐 Browser Extension

### 📌 Overview

In addition to the Python CLI tool, **GDrive Video** also provides a **Chromium-based browser extension** that lets you download private/shared videos directly from Google Drive through your browser interface.

The extension hooks into Chromium's debugging protocol to monitor network requests made by Google Drive's video player. When you navigate to a Google Drive video preview modal/page, the extension captures the media streaming data, extracts the highest-quality progressive download URL, and presents it in a simple popup for one-click download.

### ✨ Extension Features

<table>
<tr>
<td>

#### 🎬 **Download Any Video**
- Download any video shared with you
- Works even if download option is disabled
- Access restricted content

</td>
<td>

#### ⚡ **One-Click Download**
- Automatic video detection
- Simple popup interface
- Direct download to your device

</td>
</tr>
<tr>
<td>

#### 🔄 **Auto-Display**
- Automatically opens popup when videos are detected
- Seamless user experience
- Real-time stream capturing

</td>
<td>

#### 🎛️ **Easy Control**
- Toggle extension on/off per browser tab
- Quick retry button
- No extra setup needed

</td>
</tr>
</table>

### 🛠️ Extension Installation

#### Step 1: Get the Extension
```powershell
# Option A: Clone the repository (already done if you cloned gdrive-video)
git clone https://github.com/juansilvadesign/gdrive-video.git
cd gdrive-video/extension

# Option B: Or directly clone the extension folder from the project
```

#### Step 2: Load in Chromium Browser

1. Open your chromium-based browser (Chrome, Edge, Brave, etc.)
2. Navigate to your extensions page:
   - **Chrome/Edge**: `chrome://extensions/` or `edge://extensions/`
   - **Brave**: `brave://extensions/`
3. Enable **Developer mode** (toggle in top-right corner)
4. Click **Load unpacked** (or **Load extension**)
5. Select the `extension` folder from your cloned repository
6. The extension icon will appear in your toolbar

### 🎬 How to Use the Extension

#### **Video Page**

1. Navigate to any Google Drive video URL
   - Example: `https://drive.google.com/file/d/VIDEO_ID/view`
2. Click the extension icon in your toolbar
3. Click **ON** to enable URL capturing for the current tab
4. The tab will reload automatically
5. As the video loads, the popup will display:
   - 📹 Video title
   - ⬇️ Download button
6. Click the download button to save the video locally

#### **Video Modal (Folder Preview)**

1. Open any Google Drive folder
   - Example: `https://drive.google.com/drive/folders/FOLDER_ID`
2. Click the extension icon in your toolbar
3. Click **ON** to enable URL capturing for the current tab
4. The tab will reload automatically
5. Open the preview of a video by clicking on it
6. As the video loads, the popup will display available videos
7. Click the download button for the video you want
   - 💡 Multiple videos may be listed as Google Drive loads multiple files for smooth transitions

### 🧠 How the Extension Works

#### **Interception Phase**
- Uses Chrome Debugger API (`chrome.debugger`)
- Listens for `Network.requestWillBeSent` and `Network.responseReceived` events
- Detects requests to `workspacevideo-pa.clients6.google.com`
- Parses JSON responses for `progressiveTranscodes` URLs (direct MP4 links)
- Extracts video titles and metadata

#### **Pooling Phase**
- Polls the background script for captured requests
- Updates UI with new videos in real-time
- Uses `chrome.downloads.download` API for file downloads
- Persists state (enabled/disabled) per tab via `chrome.storage.local`

### 🔐 Extension Permissions

| Permission | Purpose | Usage |
|-----------|---------|-------|
| `debugger` | Network event monitoring | Intercepts video stream requests |
| `activeTab` | Current tab detection | Detects and reloads Drive tabs |
| `downloads` | File downloading | Programmatic video download |
| `storage` | State persistence | Saves on/off toggle per tab |
| `<all_urls>` | Universal access | Allows debugger attachment to any URL |

### ⚖️ Extension Disclaimer

<div align="center">

**By definition**, a cloud-based video sharing/streaming platform always downloads and saves the video into your browser for you to watch.

**This does not bypass Google Drive's security**. Google [states clearly](https://bughunters.google.com/learn/invalid-reports/google-products/5300109711245312/download-print-copy-protection-bypasses-in-drive) that this specific functionality is intended behavior and they will not try to block it in the foreseeable future.

</div>

### 📝 Extension Important Notes

- 🔓 File access permission is needed for extension functionality
- 📹 Only works on Google Drive's video preview modals or video pages
- 🔄 May list multiple videos as Google Drive preloads them
- 🌐 Works on all Chromium-based browsers (Chrome, Edge, Brave, etc.)

---

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

*Feel free to use, modify, and distribute this software! 🎉*

</div>

## 🙏 Acknowledgments

<table>
<tr>
<td align="center">
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg" width="50" height="50">
<br><strong>Python</strong>
</td>
<td align="center">
<img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/google/google-original.svg" width="50" height="50">
<br><strong>Google Drive</strong>
</td>
<td align="center">
📥
<br><strong>Requests</strong>
</td>
<td align="center">
📊
<br><strong>TQDM</strong>
</td>
</tr>
</table>

- **🐍 Python Community** - For the amazing ecosystem and tools
- **📥 Requests Library** - For reliable HTTP functionality
- **📊 TQDM** - For beautiful progress bars
- **💻 Open Source Community** - For inspiration and continuous learning

## 📞 Get in Touch

<div align="center">

### Let's Connect! 🌟

[![Email](https://img.shields.io/badge/Email-contact%40juansilva.design-red?style=for-the-badge&logo=gmail&logoColor=white)](mailto:contact@juansilva.design)
[![GitHub Issues](https://img.shields.io/badge/GitHub-Issues-black?style=for-the-badge&logo=github&logoColor=white)](https://github.com/juansilvadesign/gdrive-video/issues)

**📧 Email**: contact@juansilva.design  
**🐛 Issues**: [Create an issue](https://github.com/juansilvadesign/gdrive-video/issues) on GitHub  
**💬 Discussions**: Open for feature requests and feedback!

</div>

---

<div align="center">

### 🎉 Thank You for Using GDrive Video Downloader!

*Made with 💜 by **Juan Silva***

**⭐ If you found this project helpful, please consider giving it a star!**

![Visitors](https://visitor-badge.laobi.icu/badge?page_id=juansilvadesign.gdrive-video)

</div>
