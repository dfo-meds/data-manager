from autoinject import injector
from pipeman.dataset import DatasetController
from pipeman.attachment import UploadController
import datetime
import zirconium as zr


@injector.inject
def _generate_file_path(step, pname, fname, ext, ds, pdate, cfg: zr.ApplicationConfig = None):
    path_pattern = step.item_config['file_path_pattern'] if 'file_path_pattern' in step.item_config else "{guid}.{format_ext}"
    if "file_path_pattern_key" in step.item_config:
        path_pattern = cfg.as_str(step.item_config["file_path_pattern_key"].split("."), default=path_pattern)
    replacements = {
        "profile_name": pname,
        "format_name": fname,
        "format_ext": ext,
        "guid": ds.guid(),
        "dataset_id": ds.dataset_id,
        "revision_no": ds.revision_no,
        "created_date": datetime.datetime.now().strftime("%Y%m%d"),
        "pub_date": pdate.strftime("%Y%m%d") if pdate else "None",
    }
    for r in replacements:
        path_pattern = path_pattern.replace("{" + r + "}", str(replacements[r]))
    return path_pattern


@injector.inject
def upload_metadata(step, context, dc: DatasetController = None, uc: UploadController = None):
    ds = dc.load_dataset(context['dataset_id'], context["revision_no"])
    pname = step.item_config['profile_name']
    fname = step.item_config['format_name']
    if not dc.reg.metadata_format_exists(pname, fname):
        raise ValueError(f"Metadata format does not exist {pname} {fname}")
    if pname not in ds.profiles:
        return
    content, mime_type, encoding, ext = dc.generate_metadata_content(
        ds,
        pname,
        fname
    )
    metadata = {
        "CreationDate": datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
    }
    path = uc.upload_file(
        storage_name=step.item_config["storage_name"] if "storage_name" in step.item_config else "default",
        file_path=_generate_file_path(step, pname, fname, ext, ds, ds.revision_published_date()),
        content=content,
        content_type=mime_type,
        content_encoding=encoding,
        metadata=metadata
    )
    if path:
        step.output.append(f"Metadata uploaded to {path}")
    else:
        raise ValueError("Error uploading file")

