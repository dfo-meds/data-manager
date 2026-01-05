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
 | Field Name                     | Data Type  | i18n? | Repeatable? | Notes                                |
 |--------------------------------|------------|-------|-------------|--------------------------------------|
 | conventions                    | text       | no    | no          |                                      |
 | dataset_id_code                | text       | no    | no          | typically the DOI                    | 
 | dataset_id_desc                | text       | yes   | no          |                                      |
 | erddap_data_file_path          | text       | no    | no          |                                      |
 | erddap_data_file_pattern       | text       | no    | no          |                                      |
 | erddap_dataset_id              | text       | no    | no          |                                      |
 | institution                    | text       | no    | no          |                                      |  
 | processing_level               | text       | no    | no          |                                      |
 | program                        | text       | no    | no          |                                      |
 | project                        | text       | no    | no          |                                      |
 | standard_name_vocab            | text       | no    | no          |                                      |
 | title                          | text       | yes   | no          |                                      |                         
 | acknowledgement                | long text  | yes   | no          |                                      |                       
 | comment                        | long text  | yes   | no          |                                      |                         
 | file_storage_location          | long text  | yes   | no          |                                      |                          
 | internal_notes                 | long text  | yes   | no          |                                      |                                  
 | processing_description         | long text  | yes   | no          |                                      |                        
 | processing_environment         | long text  | yes   | no          |                                      |                          
 | purpose                        | long text  | yes   | no          |                                      |
 | references                     | long text  | yes   | no          |                                      |
 | source                         | long text  | yes   | no          |                                      |                          
 | summary                        | long text  | yes   | no          |                                      |                                   
 | geospatial_bounds              | long text  | no    | no          | (WKT compatible)                     |                                         
 | geospatial_lat_min             | decimal    | no    | no          |                                      |                                        
 | geospatial_lat_max             | decimal    | no    | no          |                                      |                             
 | geospatial_lon_min             | decimal    | no    | no          |                                      |                                           
 | geospatial_lon_max             | decimal    | no    | no          |                                      |                    
 | geospatial_vertical_min        | decimal    | no    | no          |                                      |                                         
 | geospatial_vertical_max        | decimal    | no    | no          |                                      |                    
 | date_created                   | date       | no    | no          | (YYYY-mm-dd)                         |             
 | date_issued                    | date       | no    | no          | (YYYY-mm-dd)                         |                                
 | date_modified                  | date       | no    | no          | (YYYY-mm-dd)                         |                                            
 | time_coverage_start            | datetime   | no    | no          | (YYYY-mm-ddTHH:MM:SS can omit parts) |    
 | time_coverage_end              | datetime   | no    | no          | (YYYY-mm-ddTHH:MM:SS can omit parts) |
 | is_ongoing                     | boolean    | no    | no          |                                      |                          
 | via_meds_request_form          | boolean    | no    | no          |                                      |                                  
 | metadata_maintenance_frequency | vocabulary | no    | no          | ISO Maintenance Frequency Code       | 
 | resource_maintenance_frequency | vocabulary | no    | no          | ISO Maintenance Frequency Code       |
 | spatial_representation_type    | vocabulary | no    | no          | ISO Spatial Representation Type Code |
 | status                         | vocabulary | no    | no          | ISO Progress Code                    |
 | topic_category                 | vocabulary | no    | no          | ISO Topic Category Code              |        
 | cf_standard_names              | vocabulary | no    | yes         | CF Standard Names                    |      
 | erddap_dataset_type            | vocabulary | no    | no          | ERDDAP Dataset Types                 |
 | feature_type                   | vocabulary | no    | no          | Common Data Model Data Types         |
 | goc_audience                   | vocabulary | no    | yes         | GC Audiences                         |
 | goc_collection_type            | vocabulary | no    | no          | GC Collection Types                  |                   
 | goc_publication_place          | vocabulary | no    | yes         | GC Places                            |                
 | goc_subject                    | vocabulary | no    | no          | GC Subjects                          |

NB: All vocabulary metadata fields use the short name as the value. You can find this on the Vocabularies page in 
brackets next to the more human friendly name.