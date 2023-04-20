import flask

from pipeman.db import Database
import pipeman.db.orm as orm
from autoinject import injector
from werkzeug.utils import secure_filename
import zirconium as zr
import logging
import pathlib
import uuid
import shutil
from urllib.parse import urlparse

@injector.injectable_global
class UploadController:

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.log = logging.getLogger("pipeman.uploads")

    def clean_file_name(self, name):
        name = secure_filename(name)
        return name

    def get_content(self, storage_name: str, *args, **kwargs):
        storage_config = self.config.get(("pipeman", "storage", storage_name), default=None)
        if storage_config is None:
            self.log.error(f"No configuration set for storage {storage_name}")
            return None
        if "type" not in storage_config:
            self.log.error(f"Storage type not set for {storage_name}")
            return None
        storage_config['_name'] = storage_name
        # todo: look at using universalio later (but need to add metadata/content type support)
        if storage_config["type"] == "azure_blob":
            return self._download_from_blob(storage_config, *args, **kwargs)
        elif storage_config["type"] == "azure_file":
            return self._download_from_file_share(storage_config, *args, **kwargs)
        elif storage_config["type"] == "local":
            return self._download_from_local(storage_config, *args, **kwargs)
        else:
            self.log.error(f"Unsupported storage type: {storage_config['type']}")
            return None

    def upload_file(self, storage_name: str, *args, **kwargs):
        storage_config = self.config.get(("pipeman", "storage", storage_name), default=None)
        if storage_config is None:
            self.log.error(f"No configuration set for storage {storage_name}")
            return None
        if "type" not in storage_config:
            self.log.error(f"Storage type not set for {storage_name}")
            return None
        storage_config['_name'] = storage_name
        # todo: look at using universalio later (but need to add metadata/content type support)
        if storage_config["type"] == "azure_blob":
            return self._upload_file_to_blob(storage_config, *args, **kwargs)
        elif storage_config["type"] == "azure_file":
            return self._upload_file_to_file_share(storage_config, *args, **kwargs)
        elif storage_config["type"] == "local":
            return self._upload_file_to_local(storage_config, *args, **kwargs)
        else:
            self.log.error(f"Unsupported storage type: {storage_config['type']}")
            return None

    def _download_from_blob(self, storage_config, file_path: str):
        from azure.storage.blob import ContainerClient, ContentSettings, StandardBlobTier
        from azure.identity import DefaultAzureCredential

        # Config validation
        if 'connection_string' not in storage_config:
            self.log.error(f"Share name missing for {storage_config['_name']}")
            return None
        if 'container_name' not in storage_config:
            self.log.error(f"Container name missing for {storage_config['_name']}")
            return None

        # Top level container client
        client = ContainerClient.from_connection_string(storage_config['connection_string'], storage_config['container_name'], credential=DefaultAzureCredential())

        uri = urlparse(file_path)
        path_parts = [x for x in uri.path.split('/') if x.strip(" ")]
        path = "/".join(path_parts[1:])

        blob_client = client.get_blob_client(path)
        reader = blob_client.download_blob()
        return reader

    def _upload_file_to_blob(self, storage_config, file_path: str, content, metadata: dict = None, content_type: str = None, content_encoding: str = None, length: int = None):
        from azure.storage.blob import ContainerClient, ContentSettings, StandardBlobTier
        from azure.identity import DefaultAzureCredential

        # Config validation
        if 'connection_string' not in storage_config:
            self.log.error(f"Share name missing for {storage_config['_name']}")
            return None
        if 'container_name' not in storage_config:
            self.log.error(f"Container name missing for {storage_config['_name']}")
            return None

        if "metadata" in storage_config:
            if metadata is None:
                metadata = storage_config['metadata']
            else:
                metadata.update(storage_config['metadata'])

        for key in metadata:
            metadata[key] = str(key)

        # Top level container client
        client = ContainerClient.from_connection_string(storage_config['connection_string'], storage_config['container_name'], credential=DefaultAzureCredential())

        # Calculate storage tier from config settings
        storage_tier = None if 'storage_tier' not in storage_config else getattr(StandardBlobTier, storage_config['storage_tier'])

        if (isinstance(content, bytes) or isinstance(content, str)) and length is None:
            length = len(content)
        if length == 0:
            length = None

        # Actually upload the file
        blob_client = client.upload_blob(
            name=file_path,
            data=content,
            metadata=metadata,
            length=length,
            overwrite=True,
            content_settings=ContentSettings(
                content_type=content_type,
                content_encoding=content_encoding,
            ),
            standard_blob_tier=storage_tier
        )
        return blob_client.url

    def _download_from_file_share(self, storage_config, file_path: str):
        from azure.storage.fileshare import ShareClient, ContentSettings
        from azure.identity import DefaultAzureCredential

        # Config validation
        if 'connection_string' not in storage_config:
            self.log.error(f"Connection string missing for {storage_config['_name']}")
            return None
        if 'connection_string' not in storage_config:
            self.log.error(f"Share name missing for {storage_config['_name']}")
            return None

        # Get the top-level file share client
        client = ShareClient.from_connection_string(storage_config['connection_string'], storage_config['share_name'],
                                                    credential=DefaultAzureCredential())

        uri = urlparse(file_path)
        path_parts = [x for x in uri.path.split('/') if x.strip(" ")]
        path = "/".join(path_parts[1:])

        file_client = client.get_file_client(path)
        reader = file_client.download_file()
        return reader

    def _upload_file_to_file_share(self, storage_config, file_path: str, content, metadata: dict = None, content_type: str = None, content_encoding: str = None, length: int = None):
        from azure.storage.fileshare import ShareClient, ContentSettings
        from azure.identity import DefaultAzureCredential

        # Config validation
        if 'connection_string' not in storage_config:
            self.log.error(f"Connection string missing for {storage_config['_name']}")
            return None
        if 'connection_string' not in storage_config:
            self.log.error(f"Share name missing for {storage_config['_name']}")
            return None

        if "metadata" in storage_config:
            if metadata is None:
                metadata = storage_config['metadata']
            else:
                metadata.update(storage_config['metadata'])

        for key in metadata:
            metadata[key] = str(key)

        # Get the top-level file share client
        client = ShareClient.from_connection_string(storage_config['connection_string'], storage_config['share_name'], credential=DefaultAzureCredential())

        if (isinstance(content, bytes) or isinstance(content, str)) and length is None:
            length = len(content)
        if length == 0:
            length = None

        # Recursively make the parent directories (if there are any)
        path_parts = file_path.split("/")
        dir_client = None
        for i in range(0, len(path_parts) - 1):
            if dir_client is None:
                dir_client = client.get_directory_client(path_parts[i])
            else:
                dir_client = dir_client.get_subdirectory_client(path_parts[i])
            if not dir_client.exists():
                dir_client.create_directory()

        # Actually do the file upload
        file_client = client.get_file_client(file_path)
        file_client.upload_file(
            data=content,
            length=length
        )

        # Set metadata
        file_client.set_http_headers(content_settings=ContentSettings(
            content_type=content_type,
            content_encoding=content_encoding
        ))
        file_client.set_file_metadata(metadata)
        return file_client.url

    def _safe_recursive_mkdir(self, lowest_dir, root):
        if lowest_dir.exists():
            return
        self._safe_recursive_mkdir(lowest_dir.parent, root)
        lowest_dir = lowest_dir.resolve()
        if not str(lowest_dir).startswith(root):
            raise ValueError(f"Directory {lowest_dir} outside of root {root}")
        lowest_dir.mkdir()

    def _download_from_local(self, storage_config, file_path: str):

        # Config check
        if "root_directory" not in storage_config:
            self.log.error(f"Missing root directory for {storage_config['_name']}")
            return None

        # Root directory exists check
        root = pathlib.Path(storage_config['root_directory']).resolve()
        if not root.exists():
            self.log.error(f"Root directory {root} does not exist for {storage_config['_name']}")
            return None

        if not file_path.startswith(str(root)):
            self.log.error(f"File path is not under root directory")
            return None

        return file_path


    def _upload_file_to_local(self, storage_config, file_path: str, content, metadata: dict = None, content_type: str = None, content_encoding: str = None, length: int = None):

        # Config check
        if "root_directory" not in storage_config:
            self.log.error(f"Missing root directory for {storage_config['_name']}")
            return None

        # Root directory exists check
        root = pathlib.Path(storage_config['root_directory']).resolve()
        if not root.exists():
            self.log.error(f"Root directory {root} does not exist for {storage_config['_name']}")
            return None

        # Make sure there are no weird path shenanigans
        target = (root / file_path).resolve()
        if not str(target).startswith(str(root)):
            self.log.error(f"Upload target [{target}] is outside of the root directory: [{root}] (file name: {file_path}")
            return None

        # Recursively make parent directories (only if in root directory)
        try:
            self._safe_recursive_mkdir(target.parent, str(root))
        except ValueError as ex:
            self.log.error(ex)
            return None

        # Write the file
        if isinstance(content, str):
            with open(target, "w") as h:
                h.write(content)
        elif isinstance(content, bytes):
            with open(target, "wb") as h:
                h.write(content)
        elif hasattr(content, "read"):
            with open(target, "wb") as h:
                shutil.copyfileobj(content, h)
        else:
            self.log.error(f"Unknown source object: {type(content)}")
            return None
        return str(target)


@injector.injectable
class AttachmentController:

    db: Database = None
    config: zr.ApplicationConfig = None
    canada_post: UploadController = None

    @injector.construct
    def __init__(self):
        pass

    def download_attachment(self, attachment_id):
        storage_name = self.config.get(("pipeman", "attachment", "storage_name"), default="default")
        with self.db as session:
            attachment = session.query(orm.Attachment).filter_by(id=attachment_id).first()
            if not attachment:
                return flask.abort(404)
            content = self.canada_post.get_content(attachment.storage_name or storage_name, file_path=attachment.storage_path)
            return flask.send_file(content, as_attachment=True, download_name=attachment.file_name)

    def create_attachment(self, file_upload, folder, dataset_id=None):
        storage_name = self.config.get(("pipeman", "attachment", "storage_name"), default="default")
        filename = self.canada_post.clean_file_name(file_upload.filename)
        metadata = {
            "ActualName": filename,
        }
        if dataset_id:
            metadata['DatasetID'] = dataset_id
        metadata.update(self.config.get(("pipeman", "attachment", "properties"), default={}))
        folder = self.canada_post.clean_file_name(folder)
        real_name = str(uuid.uuid4())
        if "." in filename:
            real_name += filename[filename.find("."):]
        real_path = self.canada_post.upload_file(
            storage_name,
            f"{folder}/{real_name}",
            content=file_upload.stream,
            metadata=metadata,
            content_type=file_upload.content_type,
            length=file_upload.content_length
        )
        if real_path is None:
            return None
        with self.db as session:
            att = orm.Attachment(
                file_name=filename,
                storage_path=real_path,
                dataset_id=dataset_id,
                storage_name=storage_name
            )
            session.add(att)
            session.commit()
            return att.id

    def _clean_filename(self, filename):
        filename = secure_filename(filename)
        return filename
