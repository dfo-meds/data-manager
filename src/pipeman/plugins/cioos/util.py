from pipeman.entity.entity import ValidationResult, combine_object_path


def cioos_dataset_validation(ds, object_path, profile, memo):
    errors = []
    has_owner = False
    base_resp_path = combine_object_path(object_path, [ds.field_label("responsibles")])
    for resp in ds.data("responsibles"):
        contact = resp.data("contact")
        resp_type = resp.data("role")
        if not contact:
            continue
        if resp_type and resp_type['short_name'] == 'owner':
            has_owner = True
        # Owners must have an email
        contact_path = combine_object_path(object_path, [ds.field_label("responsibles"), resp.label(), resp.field_label("contact"), contact.label()])
        if not contact.data("email"):
            errors.append(ValidationResult(
                "cioos.validation.metadata_owner_no_email",
                combine_object_path(contact_path, [contact.field_label("email")]),
                "error",
                "CIOOS-01",
                profile
            ))
        if not contact.data("id_code"):
            # Must have a name or identifier
            if not (contact.data("organization_name") or contact.data("individual_name")):
                errors.append(ValidationResult(
                    "cioos.validation.metadata_owner_no_id_code_or_name",
                    combine_object_path(contact_path, [contact.field_label("id_code")]),
                    "error",
                    "CIOOS-02",
                    profile
                ))
            else:
                errors.append(ValidationResult(
                    "cioos.validation.metadata_owner_no_id_code",
                    combine_object_path(contact_path, [contact.field_label("id_code")]),
                    "warning",
                    "CIOOS-03",
                    profile
                ))
        else:
            ident = contact.data("id_system")
            ident_path = combine_object_path(contact_path, [contact.field_label("id_system")])
            if not ident:
                errors.append(ValidationResult(
                    "cioos.validation.metadata_owner_no_id_system",
                    ident_path,
                    "error",
                    "CIOOS-04",
                    profile
                ))
            elif not ident.data("code_space"):
                    errors.append(ValidationResult(
                        "cioos.validation.metadata_owner_no_id_code_space",
                        combine_object_path(ident_path, [ident.label(), ident.field_label("code_space")]),
                        "error",
                        "CIOOS-05",
                        profile
                    ))
            else:
                is_org = bool(contact.data("organization_name")) or bool(contact.data("logo"))
                if is_org and not ident.data("code_space") == "https://ror.org/":
                    errors.append(ValidationResult(
                        "cioos.validation.metadata_owner_org_no_ror",
                        combine_object_path(ident_path, [ident.label(), ident.field_label("code_space")]),
                        "error",
                        "CIOOS-06",
                        profile
                    ))
                elif (not is_org) and not ident.data("code_space") == "https://orcid.org/":
                    errors.append(ValidationResult(
                        "cioos.validation.metadata_owner_ind_no_orcid",
                        combine_object_path(ident_path, [ident.label(), ident.field_label("code_space")]),
                        "error",
                        "CIOOS-07",
                        profile
                    ))
    if not has_owner:
        errors.append(ValidationResult(
            "cioos.validation.metadata_responsible_no_owner",
            base_resp_path,
            "error",
            "CIOOS-08",
            profile
        ))
    return errors
