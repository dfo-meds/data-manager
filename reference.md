# Permissions

| Permission Name                            | Description                                   |
|--------------------------------------------|-----------------------------------------------|
| auth_db.view.all                           | List all users                                |
| auth_db.create                             | Create a new user                             |
| auth_db.edit                               | Edit another user's account                   |
| auth_db.reset                              | Reset another user's password                 |
| entities.view                              | Access to the view entity page                |
| entities.view.all                          | Access to view all entity types               |
| entities.view.[ENTITY_NAME]                | Access to view a specific entity type         |
| entities.create                            | Access to the create entity page              |
| entities.create.all                        | Access to create all entity                   |
| entities.create.[ENTITY_NAME]              | Access to create entities of a specific type  |
| entities.edit                              | Access to the edit entity page                |
| entities.edit.all                          | Access to edit all entities                   |
| entities.edit.[ENTITY_NAME]                | Access to edit entities of a specific type    |
| entities.remove                            | Access to the remove entity page              |
| entities.remove.all                        | Access to remove all entities                 |
| entities.remove.[ENTITY_NAME]              | Access to remove entities of a specific type  |
| entities.restore                           |                                               |
| entities.restore.all                       |                                               |
| entities.restore.[ENTITY_NAME]             |                                               |
| datasets.create_api                        | Ability to create a dataset using an API call |
| datasets.view                              |                                               |
| datasets.view.deprecated                   |                                               |
| datasets.view.all                          |                                               |
| datasets.view.organization                 |                                               |
| datasets.view.assigned                     |                                               |
| datasets.create                            |                                               |
| datasets.decide.all                        |                                               |
| datasets.decide.organization               |                                               |
| datasets.decide.assigned                   |                                               |
| datasets.edit                              |                                               |
| datasets.edit.all                          |                                               |
| datasets.edit.organization                 |                                               |
| datasets.edit.assigned                     |                                               |
| datasets.remove                            |                                               |
| datasets.remove.all                        |                                               |
| datasets.remove.organization               |                                               |
| datasets.remove.assigned                   |                                               |
| datasets.restore                           |                                               |
| datasets.restore.all                       |                                               |
| datasets.restore.organization              |                                               |
| datasets.restore.assigned                  |                                               |
| datasets.activate                          |                                               |
| datasets.activate.all                      |                                               |
| datasets.activate.organization             |                                               |
| datasets.activate.assigned                 |                                               |
| datasets.publish                           |                                               |
| datasets.publish.all                       |                                               |
| datasets.publish.organization              |                                               |
| datasets.publish.assigned                  |                                               |
| datasets.post_draft_full_edit              |                                               |
| datasets.post_draft_full_edit.all          |                                               |
| datasets.post_draft_full_edit.organization |                                               |
| datasets.post_draft_full_edit.assigned     |                                               |
| action_items.view                          |                                               |
| action_items.view.completed_steps          |                                               |
| action_items.history                       |                                               |
| action_items.decide                        |                                               |
| organizations.view                         |                                               |
| organizations.edit                         |                                               |
| organizations.create                       |                                               |
| organizations.manage.any                   |                                               |
| organizations.manage.global                |                                               |
| files.upload                               |                                               |
| translations.manage                        |                                               |
| vocabularies.view                          |                                               |

# Entity Types

| Type Name              | Description |
|------------------------|-------------|
| use_constraint         |             |
| releasability          |             |
| thesaurus              |             |
| locale                 |             |
| scope                  |             |
| id_system              |             |
| goc_publishing_section |             |
| goc_publishing_org     |             |
| ref_system             |             |
| keyword                |             |
| series                 |             |
| spatial_res            |             |
| time_res               |             |
| variable               |             |
| responsibility         |             |
| maintenance            |             |
| citation               |             |
| graphic                |             |
| resource               |             |
| contact                |             |
| dist_channel           |             |

# JSON API Metadata Mapping

## Metadata Profiles Note

Currently, the system recognizes two base metadata profiles and several more specific metadata profiles

- ISO-19115-3 (aka ISO)
- ACDD 1.3 (aka ACDD)
- GoC, an extension of ISO-19115 with specific Government of Canada values
- CF, an extension of ACDD which relies on the CF Conventions for metadata
- ERDDAP, an extension of CF which provides a few additional values specific to datasets delivered by ERDDAP
- CIOOS, an extension of ISO-19115 with specific CIOOS values
- CNODC, a combination of the CF, GoC, and CIOOS metadata profiles with a few specific extensions 

The tables below include the highest level profiles that the fields are included on - all extensions also include them.


## Dataset Values
 | Field Name                     | Data Type     | i18n? | Repeatable? | Profiles    | Notes                                |
 |--------------------------------|---------------|-------|-------------|-------------|--------------------------------------|
 | conventions                    | text          | no    | no          | ACDD        |                                      |
 | dataset_id_code                | text          | no    | no          | ISO         | typically the DOI                    | 
 | dataset_id_desc                | text          | yes   | no          | ISO         |                                      |
 | erddap_data_file_path          | text          | no    | no          | ERDDAP      |                                      |
 | erddap_data_file_pattern       | text          | no    | no          | ERDDAP      |                                      |
 | erddap_dataset_id              | text          | no    | no          | ERDDAP      |                                      |
 | institution                    | text          | no    | no          | ACDD        |                                      |  
 | processing_level               | text          | no    | no          | ISO or ACDD |                                      |
 | program                        | text          | no    | no          | ACDD        |                                      |
 | project                        | text          | no    | no          | ACDD        |                                      |
 | standard_name_vocab            | text          | no    | no          | ACDD        |                                      |
 | title                          | text          | yes   | no          | ISO or ACDD |                                      |                         
 | acknowledgement                | long text     | yes   | no          | ISO or ACDD |                                      |                       
 | comment                        | long text     | yes   | no          | ISO or ACDD |                                      |                         
 | file_storage_location          | long text     | yes   | no          | CNODC       |                                      |                          
 | internal_notes                 | long text     | yes   | no          | CNODC       |                                      |                                  
 | processing_description         | long text     | yes   | no          | ISO         |                                      |                        
 | processing_environment         | long text     | yes   | no          | ISO         |                                      |                          
 | purpose                        | long text     | yes   | no          | ISO         |                                      |
 | references                     | long text     | yes   | no          | ACDD        |                                      |
 | source                         | long text     | yes   | no          | ACDD        |                                      |                          
 | summary                        | long text     | yes   | no          | ISO or ACDD |                                      |                                   
 | geospatial_bounds              | long text     | no    | no          | ISO or ACDD | (WKT compatible)                     |                                         
 | geospatial_lat_min             | decimal       | no    | no          | ISO or ACDD |                                      |                                        
 | geospatial_lat_max             | decimal       | no    | no          | ISO or ACDD |                                      |                             
 | geospatial_lon_min             | decimal       | no    | no          | ISO or ACDD |                                      |                                           
 | geospatial_lon_max             | decimal       | no    | no          | ISO or ACDD |                                      |                    
 | geospatial_vertical_min        | decimal       | no    | no          | ISO or ACDD |                                      |                                         
 | geospatial_vertical_max        | decimal       | no    | no          | ISO or ACDD |                                      |                    
 | date_created                   | date          | no    | no          | ISO or ACDD | (YYYY-mm-dd)                         |             
 | date_issued                    | date          | no    | no          | ISO or ACDD | (YYYY-mm-dd)                         |                                
 | date_modified                  | date          | no    | no          | ISO or ACDD | (YYYY-mm-dd)                         |                                            
 | time_coverage_start            | datetime      | no    | no          | ISO or ACDD | (YYYY-mm-ddTHH:MM:SS can omit parts) |    
 | time_coverage_end              | datetime      | no    | no          | ISO or ACDD | (YYYY-mm-ddTHH:MM:SS can omit parts) |
 | is_ongoing                     | boolean       | no    | no          | ISO         |                                      |                          
 | via_meds_request_form          | boolean       | no    | no          | CNODC       |                                      |                                  
 | metadata_maintenance_frequency | vocabulary    | no    | no          | ISO         | ISO Maintenance Frequency Code       | 
 | resource_maintenance_frequency | vocabulary    | no    | no          | ISO         | ISO Maintenance Frequency Code       |
 | spatial_representation_type    | vocabulary    | no    | no          | ISO         | ISO Spatial Representation Type Code |
 | status                         | vocabulary    | no    | no          | ISO         | ISO Progress Code                    |
 | topic_category                 | vocabulary    | no    | no          | ISO         | ISO Topic Category Code              |        
 | cioos_eovs                     | vocabulary    | no    | yes         | CIOOS       | COOS Essential Ocean Variables       | 
 | cf_standard_names              | vocabulary    | no    | yes         | CF          | CF Standard Names                    |      
 | erddap_dataset_type            | vocabulary    | no    | no          | ERDDAP      | ERDDAP Dataset Types                 |
 | feature_type                   | vocabulary    | no    | no          | ACDD        | Common Data Model Data Types         |
 | goc_audience                   | vocabulary    | no    | yes         | GoC         | GC Audiences                         |
 | goc_collection_type            | vocabulary    | no    | no          | GoC         | GC Collection Types                  |                   
 | goc_publication_place          | vocabulary    | no    | yes         | GoC         | GC Places                            |                
 | goc_subject                    | vocabulary    | no    | no          | GoC         | GC Subjects                          |
 | variables                      | component_ref | no    | yes         | ACDD        | Variable entities                    |
 | iso_maintenance                | component_ref | no    | yes         | ISO         | Maintenance entities                 |

## Variable Entity Values
| Field Name            | Data Type          | i18n? | Repeatable? | Profiles | Notes                                                                                                 |
|-----------------------|--------------------|-------|-------------|----------|-------------------------------------------------------------------------------------------------------|
| encoding              | vocabulary         | no    | no          | ACDD     | Character Sets                                                                                        |
| source_name [U]       | text               | no    | no          | ACDD     |                                                                                                       |
| source_data_type      | vocabulary         | no    | no          | ACDD     | Common Data Model - Data Types (packed)                                                               |
| dimensions            | text               | no    | no          | ACDD     | Comma-delimited list of dimensions for the variable                                                   |
| long_name             | text               | yes   | no          | ACDD     |                                                                                                       |
| standard_name         | vocabulary         | no    | no          | CF       | CF Standard Names                                                                                     |
| units                 | text               | no    | no          | CF       | UDUnits text string                                                                                   |
| calendar              | text               | no    | no          | CF       | CF Calendars                                                                                          |
| positive              | vocabulary         | no    | no          | CF       | CF Directions                                                                                         |
| missing_value         | text               | no    | no          | ACDD     | Value used to indicate no value provided                                                              |
| scale_factor          | float              | no    | no          | ACDD     | Value used to scale stored values                                                                     |
| add_offset            | float              | no    | no          | ACDD     | Value added to stored values                                                                          |
| destination_data_type | vocabulary         | no    | no          | ACDD     | Common Data Model - Data Types (unpacked)                                                             |
| destination_name      | text               | no    | no          | ERDDAP   |                                                                                                       |
| ioos_category         | vocabulary         | no    | no          | ERDDAP   | IOOS Categories                                                                                       |
| time_precision        | text or vocabulary | no    | no          | ERDDAP   | ERDDAP Time Precision [or an ISO format (including a T for time) with the correct level of precision] |
| time_zone             | vocabulary         | no    | no          | ERDDAP   | Time Zones                                                                                            |
| erddap_role           | vocabulary         | no    | no          | ERDDAP   | ERDDAP Variable Roles                                                                                 | 
| allow_subsets         | boolean            | no    | no          | ERDDAP   |                                                                                                       |
| actual_min            | decimal            | no    | no          | ACDD     |                                                                                                       |
| actual_max            | decimal            | no    | no          | ACDD     |                                                                                                       |
| valid_min             | decimal            | no    | no          | ACDD     |                                                                                                       |
| valid_max             | decimal            | no    | no          | ACDD     |                                                                                                       |
| cf_role               | vocabulary         | no    | no          | CF       | CF Variable Roles                                                                                     |
| comment               | long text          | no    | no          | ACDD     |                                                                                                       |
| references            | long text          | no    | no          | ACDD     |                                                                                                       |
| source                | long text          | no    | no          | ACDD     |                                                                                                       |
| coverage_content_type | vocabulary         | no    | no          | ACDD     | ISO Coverage Content Types                                                                            | 
| altitude_proxy        | boolean            | no    | no          | ERDDAP   |                                                                                                       | 
| variable_order        | integer            | no    | no          | ERDDAP   |                                                                                                       | 
| is_axis               | boolean            | no    | no          | ERDDAP   |                                                                                                       |


## Maintenance Entity Values
| Field Name | Data Type  | i18n? | Repeatable? | Profiles | Notes                  |
|------------|------------|-------|-------------|----------|------------------------|
| notes      | long text  | yes   | no          | ISO      |                        |
| date [U]   | datetime   | no    | no          | ISO      |                        |
| scope      | vocabulary | no    | no          | ISO      | ISO Maintenance Scopes |




All vocabulary metadata fields use the short name as the value. You can find this on the Vocabularies page in 
brackets next to the more human friendly name.

Multivalue fields require a list of items

Internationalized fields require a dictionary of two-letter language codes mapped to values. Use "und" for
a value that is language agnostic.
