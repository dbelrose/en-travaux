import requests
import os
import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import socket

_logger = logging.getLogger(__name__)


class OdooSyncConfig(models.Model):
    _name = 'odoo.sync.config'
    _description = 'Configuration de synchronisation Odoo.com'

    name = fields.Char('Nom', required=True)
    odoo_com_url = fields.Char('URL Odoo.com', required=True, default='https://www.odoo.com')
    username = fields.Char('Nom d\'utilisateur', required=True)
    password = fields.Char('Mot de passe', required=True)
    database_names = fields.Text('Noms des bases (une par ligne)', required=True,
                                 help="Listez les noms de vos bases Odoo.com, une par ligne")
    download_path = fields.Char('Chemin de téléchargement', required=True,
                                default='/opt/odoo/backups/')
    # Configuration proxy optionnelle
    use_proxy = fields.Boolean('Utiliser un proxy', default=False)
    proxy_host = fields.Char('Hôte proxy')
    proxy_port = fields.Integer('Port proxy')
    proxy_username = fields.Char('Utilisateur proxy')
    proxy_password = fields.Char('Mot de passe proxy')
    active = fields.Boolean('Actif', default=True)
    last_sync = fields.Datetime('Dernière synchronisation')

    @api.model
    def sync_databases(self):
        """Méthode appelée par la tâche planifiée"""
        configs = self.search([('active', '=', True)])

        for config in configs:
            try:
                config._download_databases()
                config.last_sync = fields.Datetime.now()
            except Exception as e:
                _logger.error(f"Erreur lors de la synchronisation pour {config.name}: {str(e)}")

    def _get_session_with_proxy(self):
        """Crée une session avec la configuration proxy si nécessaire"""
        session = requests.Session()
        session.timeout = 30

        if self.use_proxy and self.proxy_host:
            proxy_url = f"http://{self.proxy_host}:{self.proxy_port or 8080}"

            # Ajouter l'authentification proxy si configurée
            if self.proxy_username:
                proxy_url = f"http://{self.proxy_username}:{self.proxy_password}@{self.proxy_host}:{self.proxy_port or 8080}"

            session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            _logger.info(f"Utilisation du proxy: {self.proxy_host}:{self.proxy_port or 8080}")

        return session

    def _download_databases(self):
        """Télécharge les bases de données depuis odoo.com"""
        # Vérifier la connectivité d'abord
        try:
            socket.gethostbyname('www.odoo.com')
        except socket.gaierror:
            raise ValidationError("Impossible de résoudre www.odoo.com. Vérifiez votre connexion Internet et DNS.")

        # Créer la session avec proxy si configuré
        session = self._get_session_with_proxy()

        # Authentification - Correction de l'URL
        base_url = self.odoo_com_url.rstrip('/')
        login_url = f"{base_url}/web/login"
        login_data = {
            'login': self.username,
            'password': self.password,
        }

        # Connexion avec gestion d'erreurs
        try:
            response = session.post(login_url, data=login_data, timeout=30)
            response.raise_for_status()  # Lève une exception si erreur HTTP
        except requests.exceptions.ConnectionError as e:
            raise ValidationError(f"Erreur de connexion à odoo.com: {str(e)}")
        except requests.exceptions.Timeout:
            raise ValidationError("Timeout lors de la connexion à odoo.com")
        except requests.exceptions.RequestException as e:
            raise ValidationError(f"Erreur de requête: {str(e)}")

        if response.status_code != 200:
            raise ValidationError(f"Erreur de connexion à odoo.com: {response.status_code}")

        # Vérifier si le répertoire de destination existe
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

        # Télécharger chaque base
        database_list = [db.strip() for db in self.database_names.split('\n') if db.strip()]

        for db_name in database_list:
            try:
                self._download_single_database(session, db_name)
                _logger.info(f"Base {db_name} téléchargée avec succès")
            except Exception as e:
                _logger.error(f"Erreur lors du téléchargement de {db_name}: {str(e)}")

    def _download_single_database(self, session, db_name):
        """Télécharge une base de données spécifique"""
        # URL pour le téléchargement de backup
        base_url = self.odoo_com_url.rstrip('/')
        backup_url = f"{base_url}/web/database/backup"

        backup_data = {
            'master_pwd': 'admin',  # Mot de passe par défaut, à adapter
            'name': db_name,
            'backup_format': 'zip'
        }

        try:
            response = session.post(backup_url, data=backup_data, stream=True, timeout=300)
            response.raise_for_status()

            if response.status_code == 200:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{db_name}_backup_{timestamp}.zip"
                filepath = os.path.join(self.download_path, filename)

                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                _logger.info(f"Backup de {db_name} sauvegardé dans {filepath}")
            else:
                raise ValidationError(f"Erreur lors du téléchargement de {db_name}: {response.status_code}")

        except requests.exceptions.RequestException as e:
            raise ValidationError(f"Erreur réseau lors du téléchargement de {db_name}: {str(e)}")
        except IOError as e:
            raise ValidationError(f"Erreur d'écriture fichier pour {db_name}: {str(e)}")

    def test_connection(self):
        """Test la connexion à odoo.com avec diagnostic détaillé"""
        try:
            # Test 1: Résolution DNS
            try:
                socket.gethostbyname('www.odoo.com')
                _logger.info("✓ Résolution DNS réussie")
            except socket.gaierror:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': '✗ Erreur DNS: Impossible de résoudre www.odoo.com',
                        'type': 'danger',
                    }
                }

            # Test 2: Connexion HTTP avec proxy si configuré
            session = self._get_session_with_proxy()
            base_url = self.odoo_com_url.rstrip('/')
            login_url = f"{base_url}/web/login"

            login_data = {
                'login': self.username,
                'password': self.password,
            }

            response = session.post(login_url, data=login_data, timeout=10)

            if response.status_code == 200:
                proxy_msg = " (via proxy)" if self.use_proxy else ""
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'✓ Connexion réussie à odoo.com{proxy_msg} !',
                        'type': 'success',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'message': f'✗ Erreur HTTP: {response.status_code}',
                        'type': 'warning',
                    }
                }

        except requests.exceptions.ConnectionError as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'✗ Erreur de connexion: Vérifiez votre réseau et firewall',
                    'type': 'danger',
                }
            }
        except requests.exceptions.Timeout:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': '✗ Timeout: Le serveur met trop de temps à répondre',
                    'type': 'danger',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'✗ Erreur: {str(e)}',
                    'type': 'danger',
                }
            }
