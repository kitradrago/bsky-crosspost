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

# Global WebUI instance for singleton pattern
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
            logger.debug(f"Auth check: token={token[:8]}..., is_valid={is_auth}, tokens_in_store={len(self.authenticated_tokens)}")
            return is_auth
        logger.warning(f"❌ No Bearer token in Authorization header. Received: {auth_header[:50]}")
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
            
            if username == stored_username and password == stored_password:
                token = os.urandom(16).hex()
                self.authenticated_tokens.add(token)
                logger.info(f"✅ Login SUCCESS! New token: {token[:8]}..., total tokens in store: {len(self.authenticated_tokens)}")
                return web.json_response({'success': True, 'token': token})
            else:
                logger.warning(f"❌ Login FAILED - credentials mismatch")
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
                logger.info(f"👋 User logged out, tokens remaining: {len(self.authenticated_tokens)}")
            return web.json_response({'success': True})
        except:
            return web.json_response({'success': True})
    
    async def check_auth(self, request):
        is_auth = self._is_authenticated(request)
        logger.info(f"Auth check endpoint: authenticated={is_auth}")
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
            logger.warning(f"❌ GET /api/config - Auth failed")
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            logger.info(f"✅ GET /api/config - Auth passed, returning config")
            return web.json_response({
                'bluesky_handle': os.getenv('BLUESKY_HANDLE', ''),
                'bluesky_target_handle': os.getenv('BLUESKY_TARGET_HANDLE', ''),
                'bluesky_check_interval': int(os.getenv('BLUESKY_CHECK_INTERVAL', '300')),
                'telegram_enabled': os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true',
                'telegram_channel_id': os.getenv('TELEGRAM_CHANNEL_ID', ''),
                'discord_enabled': os.getenv('DISCORD_ENABLED', 'false').lower() == 'true',
                'discord_channel_id': os.getenv('DISCORD_CHANNEL_ID', ''),
                'furaffinity_enabled': os.getenv('FURAFFINITY_ENABLED', 'false').lower() == 'true',
                'furaffinity_submission_type': os.getenv('FURAFFINITY_SUBMISSION_TYPE', 'journal'),
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
            logger.warning(f"❌ POST /api/config - Auth failed")
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            data = await request.json()
            logger.info(f"📝 Updating config with keys: {list(data.keys())}")
            env_content = self._read_env_file()
            
            for key in ['bluesky_handle', 'bluesky_password', 'bluesky_target_handle', 'bluesky_check_interval',
                       'telegram_enabled', 'telegram_bot_token', 'telegram_channel_id',
                       'discord_enabled', 'discord_bot_token', 'discord_channel_id',
                       'furaffinity_enabled', 'furaffinity_username', 'furaffinity_password',
                       'furaffinity_submission_type', 'furaffinity_submission_category',
                       'furaffinity_submission_rating', 'furaffinity_download_images',
                       'log_level']:
                if key in data and data[key] is not None and str(data[key]) != '':
                    env_var = key.upper()
                    value_str = str(data[key]).lower() if isinstance(data[key], bool) else str(data[key])
                    env_content = self._update_env_var(env_content, env_var, value_str)
                    os.environ[env_var] = value_str
                    if len(value_str) > 20:
                        logger.info(f"  ✓ Set {env_var}={value_str[:20]}...")
                    else:
                        logger.info(f"  ✓ Set {env_var}={value_str}")
            
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
            logger.warning(f"❌ POST /api/admin/settings - Auth failed")
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
                logger.warning(f"⚠️ Log file not found: {log_file}")
                return web.json_response({'logs': [], 'total_lines': 0, 'displayed_lines': 0})
            
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
            
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return web.json_response({'logs': recent_lines, 'total_lines': len(all_lines), 'displayed_lines': len(recent_lines)})
        except Exception as e:
            logger.error(f"❌ Error in get_logs: {e}", exc_info=True)
            return web.json_response({'error': str(e), 'logs': [], 'total_lines': 0}, status=500)
    
    async def get_posts_history(self, request):
        if not self._is_authenticated(request):
            logger.warning(f"❌ GET /api/posts - Auth failed")
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            limit = int(request.rel_url.query.get('limit', '50'))
            posts = self._load_posts_history()
            logger.info(f"✅ GET /api/posts - Returning {len(posts)} posts")
            return web.json_response({'posts': posts[-limit:][::-1], 'total': len(posts)})
        except Exception as e:
            logger.error(f"Error getting posts: {e}")
            return web.json_response({'error': str(e), 'posts': [], 'total': 0}, status=500)
    
    async def get_posts_stats(self, request):
        if not self._is_authenticated(request):
            logger.warning(f"❌ GET /api/posts/stats - Auth failed")
            return web.json_response({'error': 'Unauthorized'}, status=401)
        try:
            posts = self._load_posts_history()
            logger.info(f"✅ GET /api/posts/stats - Auth passed")
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
            logger.info(f"✅ Wrote to .env file at {env_file}")
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
            except ssl.SSLError as e:
                logger.warning(f"⚠️ Existing certificate invalid, regenerating...")
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
        with open(os.path.join(os.path.dirname(__file__), 'webui.html'), 'r') as f:
            return f.read()
    
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