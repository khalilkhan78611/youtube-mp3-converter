from flask import Flask, render_template, request, send_file, url_for, redirect, jsonify
import os
import uuid
import re
import subprocess
import shutil
import logging
import threading

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("app.log"),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static', template_folder='templates')

# Configuration
TEMP_DIR = "temp_downloads"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

YT_DLP_PATH = os.path.join(os.getcwd(), "yt-dlp.exe")

# Store download progress
download_status = {}

def sanitize_filename(title):
    """Remove invalid characters from filename"""
    return re.sub(r'[\\/*?:"<>|]', "", title)

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    if 'youtube.com' in url:
        match = re.search(r'v=([^&]+)', url)
        if match:
            return match.group(1)
    elif 'youtu.be' in url:
        return url.split('/')[-1]
    return str(uuid.uuid4())  # Fallback to random ID

def update_download_status(video_id, status, percentage=0, title=None, filename=None, error=None):
    """Helper function to update download status"""
    if video_id not in download_status:
        download_status[video_id] = {
            'status': 'starting',
            'percentage': 0,
            'title': None,
            'filename': None,
            'error': None
        }
    
    download_status[video_id]['status'] = status
    if percentage is not None:
        download_status[video_id]['percentage'] = percentage
    if title is not None:
        download_status[video_id]['title'] = title
    if filename is not None:
        download_status[video_id]['filename'] = filename
    if error is not None:
        download_status[video_id]['error'] = error

def download_with_yt_dlp(youtube_url, video_id):
    """Download audio using local yt-dlp.exe"""
    try:
        # Check if yt-dlp.exe exists
        if not os.path.exists(YT_DLP_PATH):
            raise Exception(f"yt-dlp.exe not found at {YT_DLP_PATH}")
        
        update_download_status(video_id, 'getting_info', 5)
        
        # Get video title first
        title_command = f'"{YT_DLP_PATH}" --get-title "{youtube_url}"'
        title_result = subprocess.run(title_command, 
                                    shell=True,
                                    capture_output=True, 
                                    text=True)
        
        if title_result.returncode != 0:
            raise Exception("Could not get video title")
        
        video_title = sanitize_filename(title_result.stdout.strip())
        update_download_status(video_id, 'processing', 10, video_title)
        
        # Generate output path
        output_template = os.path.join(TEMP_DIR, f"{video_id}.%(ext)s")
        
        # Download command
        command = (
            f'"{YT_DLP_PATH}" -x --audio-format mp3 '
            f'--audio-quality 0 -o "{output_template}" '
            f'--newline "{youtube_url}"'
        )
        
        logger.info(f"Running command: {command}")
        update_download_status(video_id, 'downloading', 20)
        
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            universal_newlines=True
        )
        
        # Parse progress output
        for line in process.stdout:
            if '[download]' in line:
                if '%' in line:
                    try:
                        percentage = float(line.split('%')[0].split()[-1])
                        update_download_status(video_id, 'downloading', percentage)
                    except:
                        pass
        
        process.wait()
        
        if process.returncode != 0:
            error = process.stderr.read()
            raise Exception(f"yt-dlp failed: {error}")
        
        # Find the downloaded file
        for file in os.listdir(TEMP_DIR):
            if file.startswith(video_id):
                output_file = os.path.join(TEMP_DIR, file)
                break
        else:
            raise Exception("Could not find downloaded file")
        
        # Rename to final filename
        final_filename = f"{video_title}.mp3"
        final_path = os.path.join(TEMP_DIR, final_filename)
        shutil.move(output_file, final_path)
        
        update_download_status(video_id, 'completed', 100, video_title, final_filename)
        return final_filename
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        update_download_status(video_id, 'error', error=str(e))
        raise

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        youtube_url = request.form.get('youtube_url')
        
        if not youtube_url:
            return render_template('index.html', error="Please enter a YouTube URL")
        
        try:
            video_id = extract_video_id(youtube_url)
            update_download_status(video_id, 'starting')
            
            # Start download in background thread
            thread = threading.Thread(
                target=download_with_yt_dlp,
                args=(youtube_url, video_id)
            )
            thread.start()
            
            return redirect(url_for('progress', video_id=video_id))
            
        except Exception as e:
            return render_template('index.html', error=f"An error occurred: {str(e)}")
    
    return render_template('index.html')

@app.route('/progress/<video_id>')
def progress(video_id):
    return render_template('progress.html', video_id=video_id)

@app.route('/api/progress/<video_id>')
def api_progress(video_id):
    if video_id not in download_status:
        return jsonify({
            'status': 'not_found',
            'message': 'Download not found'
        }), 404
    
    progress_data = download_status[video_id]
    
    return jsonify({
        'status': progress_data['status'],
        'title': progress_data.get('title'),
        'filename': progress_data.get('filename'),
        'percentage': progress_data.get('percentage', 0),
        'error': progress_data.get('error')
    })

@app.route('/download/<filename>')
def download(filename):
    mp3_path = os.path.join(TEMP_DIR, filename)
    if os.path.exists(mp3_path):
        return send_file(mp3_path, as_attachment=True)
    else:
        return render_template('index.html', error="File not found. Please try again.")

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    logger.info(f"Starting application, yt-dlp path: {YT_DLP_PATH}")
    app.run(debug=True)