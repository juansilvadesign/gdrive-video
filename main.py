from urllib.parse import unquote, urlparse
import requests
import argparse
import sys
from tqdm import tqdm
import os
import re
import mimetypes

def extract_video_id(url_or_id: str) -> str:
    """Extracts video ID from Google Drive URL or returns the ID if already provided."""
    # If it's already just an ID (no slashes or dots), return as is
    if '/' not in url_or_id and '.' not in url_or_id:
        return url_or_id
    
    # Common Google Drive URL patterns
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',  # Standard sharing URL
        r'id=([a-zA-Z0-9_-]+)',       # URL parameter format
        r'/open\?id=([a-zA-Z0-9_-]+)', # Open format
        r'/view\?id=([a-zA-Z0-9_-]+)', # View format
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    
    # If no pattern matches, try to extract anything that looks like an ID
    # Google Drive IDs are typically 25-50 characters long, alphanumeric with dashes/underscores
    id_match = re.search(r'([a-zA-Z0-9_-]{25,50})', url_or_id)
    if id_match:
        return id_match.group(1)
    
    # If all else fails, return the original input
    return url_or_id

def validate_video_id(video_id: str) -> bool:
    """Validates if the video ID looks like a valid Google Drive ID."""
    # Google Drive IDs are typically 25-50 characters long, alphanumeric with dashes/underscores
    return bool(re.match(r'^[a-zA-Z0-9_-]{25,50}$', video_id))

def get_video_url(page_content: str, verbose: bool) -> tuple[str, str]:
    """Extracts the video playback URL and title from the page content."""
    if verbose:
        print("[INFO] Parsing video playback URL and title.")
    contentList = page_content.split("&")
    video, title = None, None
    for content in contentList:
        if content.startswith('title=') and not title:
            title = unquote(content.split('=')[-1])
        elif "videoplayback" in content and not video:
            video = unquote(content).split("|")[-1]
        if video and title:
            break

    if verbose:
        print(f"[INFO] Video URL: {video}")
        print(f"[INFO] Video Title: {title}")
    return video, title

def get_file_extension(url: str, content_type: str = None) -> str:
    """Determines the file extension based on URL and content-type."""
    # First try to get extension from the URL
    path = urlparse(url).path
    ext = os.path.splitext(path)[1]
    if ext:
        return ext

    # If no extension in URL, try to get it from content-type
    if content_type:
        ext = mimetypes.guess_extension(content_type)
        if ext:
            return ext

    # Default to .mp4 if we can't determine the extension
    return '.mp4'

def download_file(url: str, cookies: dict, filename: str, chunk_size: int, verbose: bool) -> None:
    """Downloads the file from the given URL with provided cookies, supports resuming."""
    try:
        headers = {}
        
        # Get response headers first to check content type
        if verbose:
            print("[INFO] Checking file information...")
            
        head_response = requests.head(url, cookies=cookies, timeout=30)
        content_type = head_response.headers.get('content-type')
        
        # Add file extension if not present
        if not os.path.splitext(filename)[1]:
            extension = get_file_extension(url, content_type)
            filename = filename + extension
            if verbose:
                print(f"[INFO] Adding file extension: {extension}")

        file_mode = 'wb'
        downloaded_size = 0
        
        # Check if file exists and can be resumed
        if os.path.exists(filename):
            downloaded_size = os.path.getsize(filename)
            headers['Range'] = f"bytes={downloaded_size}-"
            file_mode = 'ab'
            print(f"📂 Found existing file ({downloaded_size:,} bytes)")
            print("🔄 Resuming download...")

        if verbose:
            print(f"[INFO] Starting download from {url}")
            if downloaded_size > 0:
                print(f"[INFO] Resuming download from byte {downloaded_size:,}")

        print("⬇️  Initiating download...")
        response = requests.get(url, stream=True, cookies=cookies, headers=headers, timeout=30)
        
        if response.status_code in (200, 206):  # 200 for new downloads, 206 for partial content
            total_size = int(response.headers.get('content-length', 0)) + downloaded_size
            
            if total_size > downloaded_size:
                print(f"📊 Total file size: {total_size:,} bytes ({total_size / (1024*1024):.1f} MB)")
                
                with open(filename, file_mode) as file:
                    with tqdm(
                        total=total_size, 
                        initial=downloaded_size, 
                        unit='B', 
                        unit_scale=True, 
                        desc="📥 Downloading",
                        bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
                    ) as pbar:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                file.write(chunk)
                                pbar.update(len(chunk))
                
                print(f"\n✅ Download completed successfully!")
                print(f"📁 File saved as: {filename}")
                print(f"📊 Final size: {os.path.getsize(filename):,} bytes")
            else:
                print("✅ File already fully downloaded!")
                
        elif response.status_code == 416:  # Range not satisfiable - file already complete
            print("✅ File already fully downloaded!")
        else:
            error_messages = {
                403: "Access forbidden - Video may be private or restricted",
                404: "Video not found - Check if the video ID is correct",
                429: "Too many requests - Please wait and try again later",
                500: "Google Drive server error - Try again later"
            }
            error_msg = error_messages.get(response.status_code, f"HTTP {response.status_code}")
            print(f"❌ Download failed: {error_msg}")
            
    except requests.exceptions.Timeout:
        print("❌ Download timed out. Please check your internet connection and try again.")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error. Please check your internet connection.")
    except OSError as e:
        print(f"❌ File system error: {str(e)}")
        print("Check if you have write permissions in the current directory.")
    except Exception as e:
        print(f"❌ Unexpected error during download: {str(e)}")
        if verbose:
            import traceback
            traceback.print_exc()

def sanitize_filename(filename: str) -> str:
    """Sanitizes the filename by removing invalid characters."""
    # Remove invalid characters for Windows and Unix systems
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Remove control characters
    filename = "".join(char for char in filename if ord(char) >= 32)
    return filename.strip()

def interactive_mode() -> tuple[str, str, int, bool]:
    """Interactive mode for user input when no arguments provided."""
    print("=" * 60)
    print("   GDrive Video Downloader")
    print("=" * 60)
    print()
    
    # Get URL or ID from user
    while True:
        print("   Please paste your Google Drive video URL or ID:")
        print("   Examples:")
        print("   • https://drive.google.com/file/d/1BxBiUQN123abc456def789/view")
        print("   • 1BxBiUQN123abc456def789")
        print()
        
        url_input = input("   URL/ID: ").strip()
        if url_input:
            video_id = extract_video_id(url_input)
            if validate_video_id(video_id):
                print(f"✅ Valid video ID extracted: {video_id}")
                break
            else:
                print("❌ Invalid video ID. Please check your URL and try again.")
                print()
        else:
            print("❌ Please enter a valid URL or ID.")
            print()
    
    # Get optional output filename
    print()
    output_file = input("📁 Custom filename (optional, press Enter to use original): ").strip()
    if not output_file:
        output_file = None
    
    # Get chunk size
    print()
    chunk_input = input("⚡ Chunk size in bytes (default 8192, press Enter for default): ").strip()
    try:
        chunk_size = int(chunk_input) if chunk_input else 8192
    except ValueError:
        chunk_size = 8192
        print("⚠️  Invalid chunk size, using default (8192)")
    
    # Get verbose mode
    print()
    verbose_input = input("📝 Enable verbose mode? (y/N): ").strip().lower()
    verbose = verbose_input in ['y', 'yes', '1', 'true']
    
    print()
    print("🚀 Starting download...")
    print("=" * 60)
    
    return video_id, output_file, chunk_size, verbose

def main(video_id: str = None, output_file: str = None, chunk_size: int = 8192, verbose: bool = False) -> None:
    """Main function to process video ID and download the video file."""
    try:
        # If no video_id provided, enter interactive mode
        if not video_id:
            video_id, output_file, chunk_size, verbose = interactive_mode()
        else:
            # Extract video ID from URL if needed
            video_id = extract_video_id(video_id)
            
            # Validate the video ID
            if not validate_video_id(video_id):
                print(f"❌ Invalid video ID: {video_id}")
                print("Please check your URL or ID and try again.")
                return
        
        drive_url = f'https://drive.google.com/u/0/get_video_info?docid={video_id}&drive_originator_app=303'
        
        if verbose:
            print(f"[INFO] Accessing {drive_url}")

        print("🔍 Retrieving video information...")
        response = requests.get(drive_url)
        
        if response.status_code != 200:
            print(f"❌ Failed to access Google Drive. Status code: {response.status_code}")
            return
            
        page_content = response.text
        cookies = response.cookies.get_dict()

        video, title = get_video_url(page_content, verbose)

        if not video:
            print("❌ Unable to retrieve the video URL.")
            print("Possible reasons:")
            print("  • Video ID is incorrect")
            print("  • Video is private or restricted")
            print("  • Video has been deleted")
            print("  • Network connectivity issues")
            return

        filename = output_file if output_file else title
        filename = sanitize_filename(filename)
        
        if verbose and filename != (output_file if output_file else title):
            print(f"[INFO] Filename sanitized to: {filename}")

        print(f"📹 Video found: {title}")
        print(f"💾 Downloading as: {filename}")
        print()
        
        download_file(video, cookies, filename, chunk_size, verbose)
        
    except KeyboardInterrupt:
        print("\n")
        print("⏹️  Download interrupted by user.")
        print("You can resume the download by running the script again with the same parameters.")
    except Exception as e:
        print(f"\n❌ An error occurred: {str(e)}")
        if verbose:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="🎬 GDrive Video Downloader - Download videos from Google Drive, even view-only files!",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                           # Interactive mode
  %(prog)s 1BxBiUQN123abc456def789                  # Download by video ID
  %(prog)s "https://drive.google.com/file/d/1BxBiUQN123abc456def789/view"  # Download by URL
  %(prog)s 1BxBiUQN123abc456def789 -o "my_video.mp4"  # Custom filename
  %(prog)s 1BxBiUQN123abc456def789 -c 16384 -v       # Larger chunks, verbose mode

For more information, visit: https://github.com/juansilvadesign/gdrive-video
        """
    )
    
    parser.add_argument(
        "video_id", 
        type=str, 
        nargs='?',  # Make it optional
        help="The video ID or full URL from Google Drive (optional - will prompt if not provided)"
    )
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        help="Custom output filename (default: original video name from Google Drive)"
    )
    parser.add_argument(
        "-c", "--chunk_size", 
        type=int, 
        default=8192, 
        help="Download chunk size in bytes (default: 8192, larger = faster but more memory)"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Enable verbose mode for detailed logging"
    )
    parser.add_argument(
        "--version", 
        action="version", 
        version="%(prog)s 2.0 - Enhanced with URL support and interactive mode"
    )

    args = parser.parse_args()
    
    # Print header when in interactive mode (no video_id provided)
    if not args.video_id:
        print()
    
    try:
        main(args.video_id, args.output, args.chunk_size, args.verbose)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    
    # Keep window open when running from batch file
    if not sys.argv[1:]:  # No command line arguments (likely run from batch file)
        input("\nPress Enter to exit...")
