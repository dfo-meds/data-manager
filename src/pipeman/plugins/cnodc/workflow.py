from autoinject import injector
import zirconium as zr
from pipeman.dataset import DatasetController
import azure.storage.blob as asb
from azure.identity import DefaultAzureCredential
import datetime


@injector.inject
def upload_metadata(step, context, config: zr.ApplicationConfig = None, dc: DatasetController = None):
    ds = dc.load_dataset(context['dataset_id'], context["revision_no"])
    pname = step.item_config['profile_name']
    if pname not in ds.profiles:
        return
    fname = step.item_config['format_name']
    env = step.item_config["environment"] if "environment" in step.item_config else "production"
    default_pattern = step.item_config['pattern'] if 'pattern' in step.item_config else "{env}-{profile_name}-{format_name}-{guid}.{format_ext}"
    if not dc.reg.metadata_format_exists(pname, fname):
        raise ValueError(f"Metadata format does not exist {pname} {fname}")
    content, mime_type, encoding, ext = dc.generate_metadata_content(
        ds,
        pname,
        fname
    )
    cc = _get_container_client(config, env)
    blob_pattern = config.as_str(("cnodc", "metadata", "blob_pattern"), default=default_pattern)
    if env:
        blob_pattern = config.as_str(("cnodc", "metadata", env, "blob_pattern"), default=blob_pattern)
    allow_overwrite = config.as_bool(("cnoc", "metadata", "allow_overwrite"), default=True)
    if env:
        allow_overwrite = config.as_bool(("cnodc", "metadata", env, "allow_overwrite"), default=allow_overwrite)
    pdate = ds.revision_published_date()
    replacements = {
        "profile_name": pname,
        "format_name": fname,
        "format_ext": ext,
        "guid": ds.guid(),
        "dataset_id": ds.dataset_id,
        "revision_no": ds.revision_no,
        "created_date": datetime.datetime.now().strftime("%Y%m%d"),
        "pub_date": pdate.strftime("%Y%m%d") if pdate else "None",
        "env": env
    }
    for r in replacements:
        blob_pattern = blob_pattern.replace("{" + r + "}", str(replacements[r]))
    metadata = {
        "AccessLevel": "GENERAL",
        "SecurityLabel": "UNCLASSIFIED",
        "CreationDate": datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "ReleaseDate": "",
        "AutomatedRelease": "",
        "StoragePlan": "TIER 3",
        "PublicationPlan": "ERDDAP",
        "Program": "_METADATA",
        "Dataset": "_METADATA",
        "CostUnit": "CNODC"
    }
    cs = asb.ContentSettings(
        content_type=mime_type,
        content_encoding=encoding
    )
    blob = cc.upload_blob(
        name=blob_pattern,
        data=content,
        metadata=metadata,
        overwrite=allow_overwrite,
        length=len(content),
        content_settings=cs,
        standard_blob_tier=asb.StandardBlobTier.HOT
    )
    step.output.append(f"Metadata uploaded to {blob.url}")


def _get_container_client(config: zr.ApplicationConfig, env) -> asb.ContainerClient:
    bsc = _get_blob_service_client(config, env)
    sp = bsc.get_service_properties()
    container = config.as_str(("cnodc", "metadata", "container"))
    if env:
        container = config.as_str(("cnodc", "metadata", env, "container"), default=container)
    if not container:
        raise ValueError(f"Metadata container not specified")
    cc = bsc.get_container_client(container)
    if not cc.exists():
        raise ValueError(f"Metadata container does not exist {container}")
    return cc


def _get_blob_service_client(config: zr.ApplicationConfig, env) -> asb.BlobServiceClient:
    connect_str = config.as_str(("cnodc", "metadata", "connect_str"))
    if env:
        connect_str = config.as_str(("cnodc", "metadata", env, "connect_str"), default=connect_str)
    if connect_str.startswith("http"):
        cred = DefaultAzureCredential()
        return asb.BlobServiceClient(connect_str, credential=cred)

    return asb.BlobServiceClient.from_connection_string(connect_str)