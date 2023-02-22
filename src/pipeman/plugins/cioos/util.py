from pipeman.entity.entity import ValidationResult


def cioos_dataset_validation(ds, object_name, profile, memo):
    errors = []
    resp = ds.data("responsibles")
    has_owner = False
    base_resp_path = object_name.copy()
    base_resp_path.extend([ds.field_label("responsibles")])
    for resp in ds.data("responsibles"):
        contact = resp.data("contact")
        resp_type = resp.data("role")
        if contact and not contact.data("email"):
            obj_name = base_resp_path.copy()
            obj_name.extend([resp.label(), resp.field_label("contact"), contact.label()])
            errors.append(ValidationResult("cioos.validation.metadata_responsible_no_email", obj_name, "error", profile))
        if resp_type:
            if resp_type['short_name'] == 'owner':
                has_owner = True
    if not has_owner:
        errors.append(ValidationResult("cioos.validation.metadata_responsible_no_owner", base_resp_path, "error", profile))
    return errors

"""
CIOOS mandatory fields
-  metadata responsibilities requires at least one record (usually pointOfContact or custodian) and
   they must have an email and either a name or identifier. Identifier should be ORCID or ROR.
   codespace should be https:/ror.org/ for ROR or https://orcid.org/ for ORCID


- 
"""
