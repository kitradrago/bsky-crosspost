# webui.py source code. 

import os
import logging
import ssl
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List
import json
from aiohttp import web
import aiohttp_cors
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_webui_instance = None

class WebUI:
    def __init__(self, config, data_dir: str = "/config/data"):
        self.config = config
        self.data_dir = data_dir
        self.log_dir = os.getenv('LOG_DIR', '/config/logs')
        self.posts_history_file = os.path.join(data_dir, "posts_history.json")
        self.theme_file = os.path.join(data_dir, "theme.json")
        self.cert_dir = os.path.join(data_dir, "certs")
        self.key_file = os.path.join(data_dir, '.key')
        self.app = web.Application()
        self.authenticated_tokens = set()
        self.cipher_key = None
        self._ensure_encryption_key()
        self.setup_cors()
        self.setup_routes()
        logger.info(f"✅ WebUI initialized - log_dir: {self.log_dir}")
    
    def _ensure_encryption_key(self):
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, 'rb') as f:
                    self.cipher_key = f.read()
                logger.info(f"✅ Loaded existing encryption key")
                return
            except Exception as e:
                logger.error(f"Error reading encryption key: {e}")
        
        self.cipher_key = Fernet.generate_key()
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.key_file, 'wb') as f:
                f.write(self.cipher_key)
            logger.info(f"✅ Generated new encryption key")
        except Exception as e:
            logger.error(f"Error saving encryption key: {e}")
    
    def _encrypt_password(self, password: str) -> str:
        try:
            cipher = Fernet(self.cipher_key)
            encrypted = cipher.encrypt(password.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return password
    
    def _decrypt_password(self, encrypted: str) -> str:
        try:
            cipher = Fernet(self.cipher_key)
            decrypted = cipher.decrypt(encrypted.encode())
            return decrypted.decode()
        except Exception as e:
            logger.debug(f"Decryption error (might be plaintext): {e}")
            return encrypted
    
    def setup_cors(self):
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        })
    
    def setup_routes(self):
        self.app.router.add_get('/', self.index)
        self.app.router.add_post('/api/auth/login', self.handle_login)
        self.app.router.add_post('/api/auth/logout', self.handle_logout)
        self.app.router.add_get('/api/auth/check', self.check_auth)
        self.app.router.add_get('/api/config', self.get_config)
        self.app.router.add_post('/api/config', self.update_config)
        self.app.router.add_get('/api/config/status', self.get_status)
        self.app.router.add_get('/api/admin/settings', self.get_admin_settings)
        self.app.router.add_post('/api/admin/settings', self.update_admin_settings)
        self.app.router.add_get('/api/admin/theme', self.get_theme)
        self.app.router.add_post('/api/admin/theme', self.set_theme)
        self.app.router.add_post('/api/admin/restart', self.handle_restart)
        self.app.router.add_get('/api/logs', self.get_logs)
        self.app.router.add_get('/api/posts', self.get_posts_history)
        self.app.router.add_get('/api/posts/stats', self.get_posts_stats)
        self.app.on_startup.append(self.cleanup_old_logs)
    
    async def cleanup_old_logs(self, app):
        try:
            cutoff_date = datetime.now() - timedelta(days=90)
            if os.path.exists(self.log_dir):
                for filename in os.listdir(self.log_dir):
                    filepath = os.path.join(self.log_dir, filename)
                    if os.path.isfile(filepath):
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        if file_time < cutoff_date:
                            try:
                                os.remove(filepath)
                                logger.info(f"Deleted old log file: {filename}")
                            except Exception as e:
                                logger.warning(f"Could not delete {filename}: {e}")
        except Exception as e:
            logger.error(f"Error cleaning old logs: {e}")
    
    def _is_authenticated(self, request):
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            is_auth = token in self.authenticated_tokens
            logger.debug(f"Auth check: token={token[:8]}..., is_valid={is_auth}")
            return is_auth
        return False
    
    async def index(self, request):
        html_content = self.get_html_template()
        return web.Response(text=html_content, content_type='text/html')
    
    async def handle_login(self, request):
        try:
            data = await request.json()
            username = data.get('username', '')
            password = data.get('password', '')
            
            stored_username = os.getenv('ADMIN_USERNAME', 'admin')
            stored_password_encrypted = os.getenv('ADMIN_PASSWORD', '')
            
            if stored_password_encrypted:
                try:
                    stored_password = self._decrypt_password(stored_password_encrypted)
                except:
                    stored_password = stored_password_encrypted
            else:
                stored_password = 'admin'
            
            logger.info(f"🔑 Login attempt: username='{username}'")
            logger.debug(f"Stored username: '{stored_username}', password check: {password == stored_password}")
            
            if username == stored_username and password == stored_password:
                token = os.urandom(16).hex()
                self.authenticated_tokens.add(token)
                logger.info(f"✅ Login SUCCESS! Token: {token[:8]}...")
                return web.json_response({'success': True, 'token': token})
            else:
                logger.warning(f"❌ Login FAILED - credentials do not match")
                return web.json_response({'error': 'Invalid credentials'}, status=401)
        except Exception as e:
            logger.error(f"❌ Login error: {e}", exc_info=True)
            return web.json_response({'error': 'Login failed'}, status=500)
    
    async def handle_logout(self, request):
        try:
            data = await request.json()
            token = data.get('token', '')
            if token in self.authenticated_tokens:
                self.authenticated_tokens.remove(token)
            return web.json_response({'success': True})
        except:
            return web.json_response({'success': True})
    
    async def check_auth(self, request):
        is_auth = self._is_authenticated(request)
        return web.json_response({'authenticated': is_auth})
    
    async def get_status(self, request):
        if not self._is_authenticated(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            return web.json_response({
                'bluesky_connected': self.config.BLUESKY_HANDLE != '',
                'telegram_configured': self.config.TELEGRAM_ENABLED,
                'discord_configured': self.config.DISCORD_ENABLED,
                'furaffinity_configured': self.config.FURAFFINITY_ENABLED,
            })
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_config(self, request):
        if not self._is_authenticated(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            return web.json_response({
                'bluesky_handle': os.getenv('BLUESKY_HANDLE', ''),
                'bluesky_target_handle': os.getenv('BLUESKY_TARGET_HANDLE', ''),
                'bluesky_check_interval': int(os.getenv('BLUESKY_CHECK_INTERVAL', '300')),
                'telegram_enabled': os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true',
                'telegram_channel_id': os.getenv('TELEGRAM_CHANNEL_ID', ''),
                'discord_enabled': os.getenv('DISCORD_ENABLED', 'false').lower() == 'true',
                'discord_channel_id': os.getenv('DISCORD_CHANNEL_ID', ''),
                'furaffinity_enabled': os.getenv('FURAFFINITY_ENABLED', 'false').lower() == 'true',
                'furaffinity_submission_category': os.getenv('FURAFFINITY_SUBMISSION_CATEGORY', '1'),
                'furaffinity_submission_rating': os.getenv('FURAFFINITY_SUBMISSION_RATING', 'general'),
                'furaffinity_download_images': os.getenv('FURAFFINITY_DOWNLOAD_IMAGES', 'false').lower() == 'true',
                'log_level': os.getenv('LOG_LEVEL', 'INFO'),
            })
        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def update_config(self, request):
        if not self._is_authenticated(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            data = await request.json()
            logger.info(f"📝 Updating config with keys: {list(data.keys())}")
            env_content = self._read_env_file()
            
            for key in ['bluesky_handle', 'bluesky_password', 'bluesky_target_handle', 'bluesky_check_interval',
                       'telegram_enabled', 'telegram_bot_token', 'telegram_channel_id',
                       'discord_enabled', 'discord_bot_token', 'discord_channel_id',
                       'furaffinity_enabled', 'furaffinity_username', 'furaffinity_password',
                       'furaffinity_submission_category',
                       'furaffinity_submission_rating', 'furaffinity_download_images',
                       'log_level']:
                if key in data and data[key] is not None and str(data[key]) != '':
                    env_var = key.upper()
                    value_str = str(data[key]).lower() if isinstance(data[key], bool) else str(data[key])
                    env_content = self._update_env_var(env_content, env_var, value_str)
                    os.environ[env_var] = value_str
            
            self._write_env_file(env_content)
            logger.info(f"✅ Config updated successfully")
            return web.json_response({'success': True, 'message': 'Configuration updated. Click restart button to apply changes.'})
        except Exception as e:
            logger.error(f"Config update error: {e}", exc_info=True)
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_admin_settings(self, request):
        if not self._is_authenticated(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        return web.json_response({'admin_username': os.getenv('ADMIN_USERNAME', 'admin')})
    
    async def update_admin_settings(self, request):
        if not self._is_authenticated(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        try:
            data = await request.json()
            env_content = self._read_env_file()
            
            if 'admin_username' in data and data['admin_username']:
                env_content = self._update_env_var(env_content, 'ADMIN_USERNAME', data['admin_username'])
                os.environ['ADMIN_USERNAME'] = data['admin_username']
            
            if 'admin_password' in data and data['admin_password']:
                encrypted_password = self._encrypt_password(data['admin_password'])
                env_content = self._update_env_var(env_content, 'ADMIN_PASSWORD', encrypted_password)
                os.environ['ADMIN_PASSWORD'] = encrypted_password
            
            self._write_env_file(env_content)
            logger.info("✅ Admin settings updated")
            
            return web.json_response({'success': True, 'message': 'Admin settings updated. Click restart button to apply changes.'})
        except Exception as e:
            logger.error(f"Admin settings error: {e}", exc_info=True)
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_theme(self, request):
        try:
            if os.path.exists(self.theme_file):
                with open(self.theme_file, 'r') as f:
                    return web.json_response(json.load(f))
            return web.json_response({'theme': 'auto'})
        except Exception as e:
            logger.error(f"Error getting theme: {e}")
            return web.json_response({'theme': 'auto'})
    
    async def set_theme(self, request):
        if not self._is_authenticated(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            data = await request.json()
            theme = data.get('theme', 'auto')
            if theme not in ['light', 'dark', 'auto']:
                return web.json_response({'error': 'Invalid theme'}, status=400)
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.theme_file, 'w') as f:
                json.dump({'theme': theme}, f)
            return web.json_response({'success': True, 'theme': theme})
        except Exception as e:
            logger.error(f"Error setting theme: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_restart(self, request):
        if not self._is_authenticated(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        try:
            logger.info("🔄 RESTART REQUESTED - Container will restart in 2 seconds")
            asyncio.create_task(self._restart_container())
            return web.json_response({'success': True, 'message': 'Container restarting...'})
        except Exception as e:
            logger.error(f"Restart error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def _restart_container(self):
        await asyncio.sleep(2)
        logger.info("🔄 Executing restart...")
        os._exit(1)
    
    async def get_logs(self, request):
        if not self._is_authenticated(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        
        try:
            lines = int(request.rel_url.query.get('lines', '100'))
            log_file = os.path.join(self.log_dir, 'crosspost.log')
            
            if not os.path.exists(log_file):
                return web.json_response({'logs': [], 'total_lines': 0, 'displayed_lines': 0})
            
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
            
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return web.json_response({'logs': recent_lines, 'total_lines': len(all_lines), 'displayed_lines': len(recent_lines)})
        except Exception as e:
            logger.error(f"Error in get_logs: {e}", exc_info=True)
            return web.json_response({'error': str(e), 'logs': [], 'total_lines': 0}, status=500)
    
    async def get_posts_history(self, request):
        if not self._is_authenticated(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            limit = int(request.rel_url.query.get('limit', '50'))
            posts = self._load_posts_history()
            return web.json_response({'posts': posts[-limit:][::-1], 'total': len(posts)})
        except Exception as e:
            logger.error(f"Error getting posts: {e}")
            return web.json_response({'error': str(e), 'posts': [], 'total': 0}, status=500)
    
    async def get_posts_stats(self, request):
        if not self._is_authenticated(request):
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            posts = self._load_posts_history()
            return web.json_response({
                'total_posts': len(posts),
                'successful': sum(1 for p in posts if p.get('status') == 'success'),
                'failed': sum(1 for p in posts if p.get('status') == 'failed'),
                'telegram_sent': sum(1 for p in posts if p.get('telegram_sent')),
                'discord_sent': sum(1 for p in posts if p.get('discord_sent')),
                'furaffinity_sent': sum(1 for p in posts if p.get('furaffinity_sent')),
            })
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    def _read_env_file(self) -> str:
        env_file = '/config/.env'
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading .env: {e}")
        return ""
    
    def _write_env_file(self, content: str):
        env_file = '/config/.env'
        try:
            os.makedirs(os.path.dirname(env_file), exist_ok=True)
            with open(env_file, 'w') as f:
                f.write(content)
            logger.info(f"✅ Wrote to .env file")
        except Exception as e:
            logger.error(f"Error writing .env: {e}")
    
    def _update_env_var(self, content: str, key: str, value: str) -> str:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith(f'{key}='):
                lines[i] = f'{key}={value}'
                return '\n'.join(lines)
        lines.append(f'{key}={value}')
        return '\n'.join(lines)
    
    def _load_posts_history(self) -> List[Dict]:
        if os.path.exists(self.posts_history_file):
            try:
                with open(self.posts_history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading posts: {e}")
        return []
    
    def save_post_record(self, post: dict, telegram_sent: bool = False, discord_sent: bool = False, furaffinity_sent: bool = False, error: str = None):
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            posts = self._load_posts_history()
            posts.append({
                'uri': post.get('uri'),
                'text': post.get('text', '')[:100],
                'author': post.get('author'),
                'created_at': str(post.get('created_at')),
                'posted_at': datetime.utcnow().isoformat(),
                'telegram_sent': telegram_sent,
                'discord_sent': discord_sent,
                'furaffinity_sent': furaffinity_sent,
                'status': 'success' if (telegram_sent or discord_sent or furaffinity_sent) else 'failed',
                'error': error,
            })
            with open(self.posts_history_file, 'w') as f:
                json.dump(posts[-1000:], f)
        except Exception as e:
            logger.error(f"Error saving post: {e}")
    
    def _ensure_certificate(self):
        os.makedirs(self.cert_dir, exist_ok=True)
        cert_file = os.path.join(self.cert_dir, 'cert.pem')
        key_file = os.path.join(self.cert_dir, 'key.pem')
        
        if os.path.exists(cert_file) and os.path.exists(key_file):
            try:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(cert_file, key_file)
                logger.info(f"✅ Using existing certificate")
                return cert_file, key_file
            except ssl.SSLError:
                try:
                    os.remove(cert_file)
                    os.remove(key_file)
                except:
                    pass
        
        logger.info(f"🔐 Generating self-signed certificate...")
        cmd = f"openssl req -x509 -newkey rsa:2048 -keyout {key_file} -out {cert_file} -days 365 -nodes -subj '/CN=localhost' 2>&1"
        
        try:
            result = os.system(cmd)
            if result == 0:
                try:
                    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                    ssl_context.load_cert_chain(cert_file, key_file)
                    logger.info(f"✅ Certificate generated successfully")
                    return cert_file, key_file
                except ssl.SSLError as e:
                    logger.error(f"❌ Generated certificate invalid: {e}")
                    return None, None
            else:
                logger.error(f"❌ openssl failed")
                return None, None
        except Exception as e:
            logger.error(f"❌ Certificate error: {e}")
            return None, None
    
    def get_html_template(self) -> str:
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bluesky Crosspost Manager</title>
    <style>
        :root {--bg-primary: #ffffff; --bg-secondary: #f0f2f5; --text-primary: #333333; --text-secondary: #999999; --border-color: #e0e0e0; --card-bg: #ffffff; --input-bg: #ffffff; --input-border: #e0e0e0; --accent: #667eea; --accent-dark: #764ba2;}
        html.dark-mode {--bg-primary: #1a1a1a; --bg-secondary: #2d2d2d; --text-primary: #e0e0e0; --text-secondary: #999999; --border-color: #404040; --card-bg: #2d2d2d; --input-bg: #3a3a3a; --input-border: #404040;}
        * {margin: 0; padding: 0; box-sizing: border-box;}
        body {font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto'; background: var(--bg-secondary); color: var(--text-primary); min-height: 100vh; transition: all 0.3s;}
        .login-page {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center;}
        .login-page.hidden {display: none;}
        .login-container {background: var(--card-bg); padding: 50px 40px; border-radius: 15px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); width: 100%; max-width: 420px;}
        .login-header {text-align: center; margin-bottom: 40px;}
        .login-header h1 {font-size: 32px; color: var(--text-primary); margin-bottom: 8px;}
        .login-header p {color: var(--text-secondary); font-size: 14px;}
        .form-group {margin-bottom: 20px;}
        .form-group label {display: block; margin-bottom: 8px; color: var(--text-primary); font-weight: 600; font-size: 14px;}
        .form-group input {width: 100%; padding: 12px; border: 2px solid var(--input-border); border-radius: 8px; font-size: 14px; background: var(--input-bg); color: var(--text-primary);}
        .form-group input:focus {outline: none; border-color: var(--accent);}
        .login-btn {width: 100%; padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;}
        .login-btn:hover {transform: translateY(-2px);}
        .dashboard {display: none;}
        .dashboard:not(.hidden) {display: block;}
        .navbar {background: var(--card-bg); border-bottom: 1px solid var(--border-color); padding: 20px 40px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1); position: sticky; top: 0; z-index: 100;}
        .navbar-left {display: flex; align-items: center; gap: 20px;}
        .navbar h1 {color: var(--text-primary); font-size: 24px; margin: 0;}
        .status-indicator {width: 10px; height: 10px; border-radius: 50%; background: #4caf50; animation: pulse 2s infinite; display: inline-block;}
        @keyframes pulse {0%, 100% {opacity: 1;} 50% {opacity: 0.5;}}
        .navbar-right {display: flex; gap: 15px; align-items: center; flex-wrap: wrap;}
        .restart-banner {display: flex; align-items: center; gap: 10px; background: #fff3cd; color: #856404; padding: 10px 15px; border-radius: 8px; font-size: 14px; font-weight: 600;}
        .restart-banner.hidden {display: none;}
        .restart-btn {padding: 6px 12px; background: #ff6b6b; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600;}
        .restart-btn:hover {background: #ff5252;}
        .theme-toggle {padding: 8px 16px; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600;}
        .theme-toggle:hover {background: var(--accent); color: white;}
        .logout-btn {padding: 10px 20px; background: #ff6b6b; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600;}
        .logout-btn:hover {background: #ff5252;}
        .container {max-width: 1200px; margin: 0 auto; padding: 40px 20px;}
        .tabs {display: flex; gap: 10px; margin-bottom: 30px; border-bottom: 2px solid var(--border-color);}
        .tab-btn {padding: 15px 20px; border: none; background: none; cursor: pointer; font-size: 14px; font-weight: 600; color: var(--text-secondary); transition: all 0.3s; border-bottom: 3px solid transparent; margin-bottom: -2px;}
        .tab-btn:hover {color: var(--accent);}
        .tab-btn.active {color: var(--accent); border-bottom-color: var(--accent);}
        .page {display: none;}
        .page.active {display: block; animation: fadeIn 0.3s;}
        @keyframes fadeIn {from {opacity: 0; transform: translateY(10px);} to {opacity: 1; transform: translateY(0);}}
        .card {background: var(--card-bg); padding: 30px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; border: 1px solid var(--border-color);}
        .card-header {display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;}
        .card h2 {color: var(--text-primary); margin-bottom: 0; font-size: 20px;}
        .form-row {display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 25px; margin-bottom: 20px;}
        .form-field {display: flex; flex-direction: column;}
        .form-field label {font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px;}
        .form-field input, .form-field select {padding: 10px 12px; border: 2px solid var(--input-border); border-radius: 8px; font-size: 13px; font-family: inherit; background: var(--input-bg); color: var(--text-primary);}
        .form-field input:focus, .form-field select:focus {outline: none; border-color: var(--accent);}
        .form-field input[type="checkbox"] {width: auto; margin-right: 8px;}
        .helper-text {font-size: 12px; color: var(--text-secondary); margin-top: 5px;}
        .toggle-switch {position: relative; display: inline-block; width: 60px; height: 34px;}
        .toggle-switch input {opacity: 0; width: 0; height: 0;}
        .toggle-slider {position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: 0.4s; border-radius: 34px;}
        .toggle-slider:before {position: absolute; content: ""; height: 26px; width: 26px; left: 4px; bottom: 4px; background-color: white; transition: 0.4s; border-radius: 50%;}
        input:checked + .toggle-slider {background-color: var(--accent);}
        input:checked + .toggle-slider:before {transform: translateX(26px);}
        .btn {padding: 12px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.3s;}
        .btn-primary {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;}
        .btn-primary:hover {transform: translateY(-2px); box-shadow: 0 8px 16px rgba(102,126,234,0.4);}
        .btn-secondary {background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border-color);}
        .btn-secondary:hover {background: var(--accent); color: white;}
        .alert {padding: 15px; border-radius: 8px; margin-bottom: 20px; font-size: 14px;}
        .alert.success {background: #d4edda; color: #155724; border: 1px solid #c3e6cb;}
        .alert.error {background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;}
        .stats-grid {display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; margin-bottom: 30px;}
        .stat-card {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 12px; text-align: center;}
        .stat-card h3 {font-size: 12px; margin-bottom: 10px; opacity: 0.9;}
        .stat-card .number {font-size: 36px; font-weight: bold;}
        .logs-container {background: #1e1e1e; color: #d4d4d4; padding: 20px; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 12px; max-height: 600px; overflow-y: auto; margin-top: 20px; border: 1px solid #3e3e3e;}
        html.dark-mode .logs-container {background: #0a0a0a; border-color: #2a2a2a;}
        .log-line {margin-bottom: 5px; white-space: pre-wrap; word-break: break-word; line-height: 1.4;}
        .posts-table {width: 100%; border-collapse: collapse; margin-top: 20px;}
        .posts-table th {background: var(--bg-secondary); padding: 12px; text-align: left; border-bottom: 2px solid var(--border-color); font-weight: 600; color: var(--text-primary);}
        .posts-table td {padding: 12px; border-bottom: 1px solid var(--border-color);}
        .posts-table tr:hover {background: var(--bg-secondary);}
        .status-badge {display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;}
        .status-badge.success {background: #d4edda; color: #155724;}
        .status-badge.failed {background: #f8d7da; color: #721c24;}
        .log-controls {display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; align-items: center;}
        .disabled-state {opacity: 0.6; pointer-events: none;}
        @media (max-width: 768px) {.navbar {flex-direction: column; gap: 15px;} .form-row {grid-template-columns: 1fr;} .container {padding: 20px 15px;} .card-header {flex-direction: column; align-items: flex-start; gap: 15px;}}
    </style>
</head>
<body>
    <div class="login-page" id="loginPage">
        <div class="login-container">
            <div class="login-header"><h1>🚀 Bluesky Crosspost</h1><p>Automatically share your Bluesky posts</p></div>
            <form onsubmit="handleLogin(event)">
                <div class="form-group"><label>Username</label><input type="text" id="username" placeholder="Enter username" required autofocus></div>
                <div class="form-group"><label>Password</label><input type="password" id="password" placeholder="Enter password" required></div>
                <button type="submit" class="login-btn">Sign In</button>
            </form>
        </div>
    </div>
    
    <div class="dashboard hidden" id="dashboard">
        <div class="navbar"><div class="navbar-left"><h1>🚀 Bluesky Crosspost</h1><span class="status-indicator"></span></div><div class="navbar-right"><div id="restartBanner" class="restart-banner hidden">⚠️ Settings changed <button class="restart-btn" onclick="restartContainer()">Restart Now</button></div><button class="theme-toggle" onclick="toggleTheme()">🌙</button><button class="logout-btn" onclick="handleLogout()">Sign Out</button></div></div>
        <div class="container">
            <div class="tabs"><button class="tab-btn active" onclick="showTab('setup')">⚙️ Setup</button><button class="tab-btn" onclick="showTab('activity')">📊 Activity</button><button class="tab-btn" onclick="showTab('logs')">📋 Logs</button><button class="tab-btn" onclick="showTab('admin')">🔐 Admin</button></div>
            <div class="page active" id="setupPage"><div class="card"><div class="card-header"><h2>🔐 Bluesky Account</h2></div><div class="form-row"><div class="form-field"><label>Bluesky Handle</label><input type="text" id="blueskyHandle" placeholder="example.bsky.social"></div><div class="form-field"><label>App Password</label><input type="password" id="blueskyPassword" placeholder="••••••••" autocomplete="new-password"></div></div><div class="form-row"><div class="form-field"><label>Account to Monitor</label><input type="text" id="blueskyTargetHandle" placeholder="furthemore.org"></div><div class="form-field"><label>Check Interval (sec)</label><input type="number" id="blueskyCheckInterval" placeholder="300" min="10"></div></div></div><div class="card"><div class="card-header"><h2>💬 Telegram</h2><label class="toggle-switch"><input type="checkbox" id="telegramEnabled"><span class="toggle-slider"></span></label></div><div id="telegramSettings"><div class="form-row"><div class="form-field"><label>Bot Token</label><input type="password" id="telegramBotToken" placeholder="123456:ABC-DEF..." autocomplete="new-password"></div><div class="form-field"><label>Channel ID</label><input type="text" id="telegramChannelId" placeholder="-1001234567890"></div></div></div></div><div class="card"><div class="card-header"><h2>🎮 Discord</h2><label class="toggle-switch"><input type="checkbox" id="discordEnabled"><span class="toggle-slider"></span></label></div><div id="discordSettings"><div class="form-row"><div class="form-field"><label>Bot Token</label><input type="password" id="discordBotToken" placeholder="MTA4NzQ1..." autocomplete="new-password"></div><div class="form-field"><label>Channel ID</label><input type="text" id="discordChannelId" placeholder="1087459487405..."></div></div></div></div><div class="card"><div class="card-header"><h2>🐾 FurAffinity</h2><label class="toggle-switch"><input type="checkbox" id="furAffinityEnabled"><span class="toggle-slider"></span></label></div><div id="furAffinitySettings"><div class="form-row"><div class="form-field"><label>Username</label><input type="text" id="furAffinityUsername" placeholder="your_username"></div><div class="form-field"><label>Password</label><input type="password" id="furAffinityPassword" placeholder="••••••••" autocomplete="new-password"></div></div><div class="form-row"><div class="form-field"><label>Image Category</label><select id="furAffinitySubmissionCategory"><option value="1">Artwork/Digital</option><option value="2">Photography</option><option value="3">Traditional Art</option><option value="4">Sculpture</option><option value="5">Other</option></select><div class="helper-text">Used for image submissions only</div></div></div><div class="form-row"><div class="form-field"><label>Rating</label><select id="furAffinitySubmissionRating"><option value="general">General</option><option value="mature">Mature</option><option value="adult">Adult</option></select></div><div class="form-field"><label><input type="checkbox" id="furAffinityDownloadImages"> Download & Submit Images</label><div class="helper-text">Auto-detect images in posts and submit as images when available, otherwise post as journal</div></div></div></div></div><button class="btn btn-primary" onclick="saveConfig()" style="margin-top: 20px;">💾 Save Settings</button><div id="setupAlert"></div></div>
            <div class="page" id="activityPage"><div class="card"><h2>📊 Activity Overview</h2><div class="stats-grid"><div class="stat-card"><h3>Posts Processed</h3><div class="number" id="totalPosts">-</div></div><div class="stat-card"><h3>Successful</h3><div class="number" id="successfulPosts">-</div></div><div class="stat-card"><h3>Telegram</h3><div class="number" id="telegramCount">-</div></div><div class="stat-card"><h3>Discord</h3><div class="number" id="discordCount">-</div></div><div class="stat-card"><h3>FurAffinity</h3><div class="number" id="furAffinityCount">-</div></div></div></div><div class="card"><h2>📝 Recent Posts</h2><table class="posts-table"><thead><tr><th>Date & Time</th><th>Post</th><th>Status</th><th>Telegram</th><th>Discord</th><th>FurAffinity</th></tr></thead><tbody id="postsTableBody"><tr><td colspan="6" style="text-align: center; padding: 40px;">Loading...</td></tr></tbody></table></div></div>
            <div class="page" id="logsPage"><div class="card"><h2>📋 System Logs</h2><div class="log-controls"><div class="form-field" style="margin: 0; flex: 1; min-width: 150px;"><label>Show last:</label><select id="logLines" onchange="loadLogs()" style="margin-top: 4px;"><option value="50">50 lines</option><option value="100" selected>100 lines</option><option value="200">200 lines</option><option value="500">500 lines</option></select></div><button class="btn btn-secondary" onclick="loadLogs()" style="margin-top: 22px;">🔄 Refresh Logs</button><label style="margin-top: 22px;"><input type="checkbox" id="autoRefreshLogs"> Auto-refresh</label></div><div class="logs-container" id="logsContainer"><div class="log-line">Loading...</div></div></div></div>
            <div class="page" id="adminPage"><div class="card"><h2>🔐 Admin Settings</h2><div class="form-row"><div class="form-field"><label>Admin Username</label><input type="text" id="adminUsername" placeholder="admin" autocomplete="off"><div class="helper-text">Username for web interface</div></div><div class="form-field"><label>Admin Password</label><input type="password" id="adminPassword" placeholder="••••••••" autocomplete="new-password"><div class="helper-text">Password for web interface (will be encrypted)</div></div></div><button class="btn btn-primary" onclick="saveAdminSettings()" style="margin-top: 20px;">💾 Save Admin Settings</button><div id="adminAlert"></div></div></div>
        </div>
    </div>
    <script>
        let authToken = localStorage.getItem('authToken');
        let refreshInterval = null;
        
        window.onload = async function() {
            loadTheme();
            if (authToken) {
                try {
                    const res = await fetch('/api/auth/check', {headers: {'Authorization': 'Bearer ' + authToken}});
                    if (res.ok) {
                        const data = await res.json();
                        if (data.authenticated) {
                            showDashboard();
                            await loadConfig();
                            await loadPosts();
                            await loadLogs();
                            setupToggleListeners();
                            refreshInterval = setInterval(() => {
                                const tab = document.querySelector('.tab-btn.active');
                                if (tab && tab.textContent.includes('Activity')) loadPosts();
                            }, 5000);
                            return;
                        }
                    }
                } catch (e) {
                    console.error("Token check failed:", e);
                }
            }
            showLogin();
        };
        
        function setupToggleListeners() {
            ['telegram', 'discord', 'furAffinity'].forEach(service => {
                const el = document.getElementById(service + 'Enabled');
                if (el) el.addEventListener('change', function() {
                    const settingsEl = document.getElementById(service.charAt(0).toUpperCase() + service.slice(1) + 'Settings');
                    if (settingsEl) settingsEl.classList.toggle('disabled-state', !this.checked);
                });
            });
        }
        
        function loadTheme() {
            fetch('/api/admin/theme').then(r => r.json()).then(data => {
                const theme = data.theme || 'auto';
                if (theme === 'dark' || (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                    document.documentElement.classList.add('dark-mode');
                }
            });
        }
        
        function toggleTheme() {
            const isDark = document.documentElement.classList.toggle('dark-mode');
            fetch('/api/admin/theme', {method: 'POST', headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken}, body: JSON.stringify({theme: isDark ? 'dark' : 'light'})});
        }
        
        function showLogin() {
            document.getElementById('loginPage').classList.remove('hidden');
            document.getElementById('dashboard').classList.add('hidden');
        }
        
        function showDashboard() {
            document.getElementById('loginPage').classList.add('hidden');
            document.getElementById('dashboard').classList.remove('hidden');
        }
        
        function showTab(tab) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(tab + 'Page').classList.add('active');
            event.target.classList.add('active');
        }
        
        function showRestartBanner() {
            document.getElementById('restartBanner').classList.remove('hidden');
        }
        
        async function restartContainer() {
            if (confirm('🔄 This will restart the container. Continue?')) {
                const res = await apiCall('/api/admin/restart', 'POST');
                const r = await res.json();
                if (res.ok) {
                    alert('✅ Container restarting...');
                    setTimeout(() => location.reload(), 5000);
                }
            }
        }
        
        async function handleLogin(e) {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username, password})
            });
            if (res.ok) {
                const data = await res.json();
                authToken = data.token;
                localStorage.setItem('authToken', authToken);
                showDashboard();
                await loadConfig();
                await loadPosts();
                await loadLogs();
                setupToggleListeners();
                refreshInterval = setInterval(() => {
                    const tab = document.querySelector('.tab-btn.active');
                    if (tab && tab.textContent.includes('Activity')) loadPosts();
                }, 5000);
            } else {
                alert('❌ Invalid credentials');
            }
        }
        
        async function handleLogout() {
            await fetch('/api/auth/logout', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken},
                body: JSON.stringify({token: authToken})
            });
            authToken = null;
            localStorage.removeItem('authToken');
            if (refreshInterval) clearInterval(refreshInterval);
            showLogin();
        }
        
        async function apiCall(url, method = 'GET', body) {
            const opts = {method, headers: {'Authorization': 'Bearer ' + authToken}};
            if (body) {
                opts.headers['Content-Type'] = 'application/json';
                opts.body = JSON.stringify(body);
            }
            return fetch(url, opts);
        }
        
        async function loadConfig() {
            const res = await apiCall('/api/config');
            const cfg = await res.json();
            document.getElementById('blueskyHandle').value = cfg.bluesky_handle || '';
            document.getElementById('blueskyTargetHandle').value = cfg.bluesky_target_handle || '';
            document.getElementById('blueskyCheckInterval').value = cfg.bluesky_check_interval || '300';
            document.getElementById('telegramEnabled').checked = cfg.telegram_enabled || false;
            document.getElementById('telegramChannelId').value = cfg.telegram_channel_id || '';
            document.getElementById('discordEnabled').checked = cfg.discord_enabled || false;
            document.getElementById('discordChannelId').value = cfg.discord_channel_id || '';
            document.getElementById('furAffinityEnabled').checked = cfg.furaffinity_enabled || false;
            document.getElementById('furAffinitySubmissionCategory').value = cfg.furaffinity_submission_category || '1';
            document.getElementById('furAffinitySubmissionRating').value = cfg.furaffinity_submission_rating || 'general';
            document.getElementById('furAffinityDownloadImages').checked = cfg.furaffinity_download_images || false;
            const adm = await (await apiCall('/api/admin/settings')).json();
            document.getElementById('adminUsername').value = adm.admin_username || '';
            
            document.getElementById('telegramSettings').classList.toggle('disabled-state', !cfg.telegram_enabled);
            document.getElementById('discordSettings').classList.toggle('disabled-state', !cfg.discord_enabled);
            document.getElementById('furAffinitySettings').classList.toggle('disabled-state', !cfg.furaffinity_enabled);
        }
        
        async function saveConfig() {
            const res = await apiCall('/api/config', 'POST', {
                bluesky_handle: document.getElementById('blueskyHandle').value,
                bluesky_password: document.getElementById('blueskyPassword').value,
                bluesky_target_handle: document.getElementById('blueskyTargetHandle').value,
                bluesky_check_interval: parseInt(document.getElementById('blueskyCheckInterval').value) || 300,
                telegram_enabled: document.getElementById('telegramEnabled').checked,
                telegram_bot_token: document.getElementById('telegramBotToken').value,
                telegram_channel_id: document.getElementById('telegramChannelId').value,
                discord_enabled: document.getElementById('discordEnabled').checked,
                discord_bot_token: document.getElementById('discordBotToken').value,
                discord_channel_id: document.getElementById('discordChannelId').value,
                furaffinity_enabled: document.getElementById('furAffinityEnabled').checked,
                furaffinity_username: document.getElementById('furAffinityUsername').value,
                furaffinity_password: document.getElementById('furAffinityPassword').value,
                furaffinity_submission_category: document.getElementById('furAffinitySubmissionCategory').value,
                furaffinity_submission_rating: document.getElementById('furAffinitySubmissionRating').value,
                furaffinity_download_images: document.getElementById('furAffinityDownloadImages').checked
            });
            const r = await res.json();
            document.getElementById('setupAlert').innerHTML = res.ok ? '<div class="alert success">✅ ' + r.message + '</div>' : '<div class="alert error">❌ ' + r.error + '</div>';
            if (res.ok) showRestartBanner();
        }
        
        async function saveAdminSettings() {
            const u = document.getElementById('adminUsername').value;
            const p = document.getElementById('adminPassword').value;
            if (!u && !p) {alert('Enter username or password'); return;}
            const res = await apiCall('/api/admin/settings', 'POST', {admin_username: u, admin_password: p});
            const r = await res.json();
            document.getElementById('adminAlert').innerHTML = res.ok ? '<div class="alert success">✅ ' + r.message + '</div>' : '<div class="alert error">❌ ' + r.error + '</div>';
            if (res.ok) {
                document.getElementById('adminPassword').value = '';
                showRestartBanner();
            }
        }
        
        async function loadPosts() {
            const stats = await (await apiCall('/api/posts/stats')).json();
            const posts = await (await apiCall('/api/posts?limit=50')).json();
            document.getElementById('totalPosts').textContent = stats.total_posts || 0;
            document.getElementById('successfulPosts').textContent = stats.successful || 0;
            document.getElementById('telegramCount').textContent = stats.telegram_sent || 0;
            document.getElementById('discordCount').textContent = stats.discord_sent || 0;
            document.getElementById('furAffinityCount').textContent = stats.furaffinity_sent || 0;
            const tbody = document.getElementById('postsTableBody');
            tbody.innerHTML = posts.posts && posts.posts.length ? posts.posts.map(p => '<tr><td>' + new Date(p.posted_at).toLocaleString() + '</td><td>' + p.text.substring(0, 50) + '</td><td><span class="status-badge ' + p.status + '">' + p.status + '</span></td><td>' + (p.telegram_sent ? '✅' : '⏸️') + '</td><td>' + (p.discord_sent ? '✅' : '⏸️') + '</td><td>' + (p.furaffinity_sent ? '✅' : '⏸️') + '</td></tr>').join('') : '<tr><td colspan="6" style="text-align: center; padding: 40px;">No posts</td></tr>';
        }
        
        async function loadLogs() {
            const lines = document.getElementById('logLines').value || '100';
            const res = await apiCall('/api/logs?lines=' + lines);
            if (!res.ok) {
                document.getElementById('logsContainer').innerHTML = '<div class="log-line">Error ' + res.status + ' loading logs</div>';
                return;
            }
            const data = await res.json();
            const c = document.getElementById('logsContainer');
            c.innerHTML = data.logs && data.logs.length ? data.logs.map(l => '<div class="log-line">' + l.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</div>').join('') : '<div class="log-line">No logs available</div>';
            c.scrollTop = c.scrollHeight;
        }
    </script>
</body>
</html>'''
    
    async def start(self, port: int = 2759):
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        cert_file, key_file = self._ensure_certificate()
        
        if cert_file and key_file:
            try:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(cert_file, key_file)
                site = web.TCPSite(runner, '0.0.0.0', port, ssl_context=ssl_context)
                logger.info(f"✅ Web UI started on https://0.0.0.0:{port}")
            except ssl.SSLError as e:
                logger.error(f"SSL error: {e}. Using HTTP")
                site = web.TCPSite(runner, '0.0.0.0', port)
        else:
            site = web.TCPSite(runner, '0.0.0.0', port)
            logger.warning(f"⚠️ Web UI started on http://0.0.0.0:{port}")
        
        await site.start()


def create_webui(config, data_dir: str = "/config/data") -> WebUI:
    global _webui_instance
    if _webui_instance is None:
        _webui_instance = WebUI(config, data_dir)
        logger.info(f"✅ Created WebUI singleton")
    return _webui_instance