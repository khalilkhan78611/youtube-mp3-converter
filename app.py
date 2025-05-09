import yt_dlp
from flask import Flask, jsonify, request, send_from_directory, render_template
import logging
from threading import Lock
import os

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Thread lock for yt-dlp operations
yt_lock = Lock()

def download_with_yt_dlp(video_id):
    """
    Robust YouTube title extraction with multiple fallback methods
    Returns: Video title or raises exception
    """
    ydl_opts = {
        'quiet': True,
        'force_ipv4': True,
        'socket_timeout': 15,
        'extractor_args': {'youtube': {'skip': ['dash', 'hls']}},
        'noplaylist': True,
    }

    methods = [
        {'extract_flat': False},  # Full extraction first
        {'extract_flat': True},   # Then try flat extraction
        {'extract_flat': True, 'process': False}  # Minimal processing
    ]

    last_error = None
    
    with yt_lock:  # Prevent concurrent yt-dlp access
        for method in methods:
            try:
                current_opts = {**ydl_opts, **method}
                with yt_dlp.YoutubeDL(current_opts) as ydl:
                    info = ydl.extract_info(
                        f'https://youtu.be/{video_id}',
                        download=False
                    )
                    
                    if info and 'title' in info:
                        logger.info(f"Successfully extracted title for {video_id} via method {method}")
                        return info['title']
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Method {method} failed for {video_id}: {last_error}")
                continue
    
    logger.error(f"All extraction methods failed for {video_id}")
    raise Exception(f"Could not get video title. Last error: {last_error}")

@app.route('/')
def index():
    """Main page with simple interface"""
    return render_template('index.html')

@app.route('/progress/<video_id>')
def progress(video_id):
    """API endpoint to get video title"""
    try:
        title = download_with_yt_dlp(video_id)
        return jsonify({
            'status': 'success',
            'video_id': video_id,
            'title': title
        })
    except Exception as e:
        logger.error(f"Failed to process {video_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'video_id': video_id,
            'message': str(e)
        }), 500

@app.route('/static/<path:filename>')
def static_files(filename):
    """Static file serving"""
    static_folder = os.path.join(os.path.dirname(__file__), 'static')
    return send_from_directory(static_folder, filename)

if __name__ == '__main__':
    # Check essential dependencies
    try:
        import yt_dlp
        logger.info("All dependencies are available")
    except ImportError as e:
        logger.critical(f"Missing dependency: {str(e)}")
        exit(1)
    
    # Create required directories
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Run the app
    app.run(host='0.0.0.0', port=5001, threaded=True, debug=True)
