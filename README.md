<div align="center">

# 📥💾 GDrive Video

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

> **💡 Tip**: Using a virtual environment is highly recommended to avoid dependency conflicts!

#### 1️⃣ Clone the Repository
```powershell
git clone https://github.com/juansilvadesign/gdrive-video.git
cd gdrive-video
```


#### 2️⃣ Set Up Virtual Environment (Recommended)
```powershell
# Install virtualenv if you haven't already
pip install virtualenv

# Create virtual environment
virtualenv .env

# Activate virtual environment
.env\Scripts\activate
```

#### 3️⃣ Install Dependencies
```powershell
pip install -r requirements.txt
```

#### 4️⃣ Launch Application
```powershell
python main.py
```

#### 5️⃣ Deactivate Environment (When Done)
```powershell
deactivate
```

### 🎯 One-Line Installation
```powershell
git clone https://github.com/juansilvadesign/gdrive-video.git && cd gdrive-video && pip install -r requirements.txt && python main.py
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
python main.py <video_id>
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
python main.py 1BxBiUQN123abc456def789

# Custom output filename
python main.py 1BxBiUQN123abc456def789 -o "my_video.mp4"

# Larger chunk size for faster download
python main.py 1BxBiUQN123abc456def789 -c 8192

# Verbose mode for debugging
python main.py 1BxBiUQN123abc456def789 -v

# Combined options
python main.py 1BxBiUQN123abc456def789 -o "important_video.mp4" -c 4096 -v
```

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


## 📄 License

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

*Made with 💜 by **Juan Pablo***

**⭐ If you found this project helpful, please consider giving it a star!**

![Visitors](https://visitor-badge.laobi.icu/badge?page_id=juansilvadesign.gdrive-video)

</div>