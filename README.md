# Data Management Dashboard

TODO: Better name

## Scope

This project aims to create a data management tool that will allow organizations which
produce and distribute scientific data to easily manage the metadata and the workflows
of their data. In particular, the following problem statements will be addressed in
two different domains.

### Domain A - Metadata Management

1. How can we create, validate, approve, and version control our metadata?
2. How can we produce metadata files which match the appropriate metadata standards?
3. How can we track and manage changes to configuration files?
4. How can we reduce duplication of effort in managing these files?
5. How can we automate the deployment of metadata to various computer systems that require them?


### Domain B - Data Management

1. How can we handle the review and approval of new data files into our datasets with ongoing updates?
2. How can we validate these new data files as to their suitability for distribution?
3. How can we accept new data from external sources in a more robust fashion than FTP?
4. How can we streamline manual quality assurance processes?
5. How can we connect the automated data processing and assembly processes to distribution systems?
6. How can we monitor and report on such automated processes?
7. How can we integrate our system with legacy systems to enable a phased migration to the new system?


## Solution

Data catalog tools like CKAN are focused on the public cataloging and delivery of data to users. 
However, there are additional needs for organizations that manage data in terms of managing the
workflow to bring data to the public, managing and verifying metadata changes, and integrating 
these changes into multiple systems. In essence, this is the distinction between something like
an Application Catalog for software versus version control and/or continuous integration platforms 
for organizing and testing releases prior to making them available to the public. 

We propose the creation of an open-source application that allows users to manage and oversee their
data delivery processes. Of note, scientific data processing is often dataset-specific, so such a 
solution will not offer data processing per se. Instead, it should focus on orchestrating and 
streamlining the delivery of data and metadata changes to datasets and the related systems for
data and metadata delivery.

## Proposed Features

1. A multilingual web interface for users as well as an API for programmatic access (Flask? Starlet?)
2. Robust user and API key management, suitable for use in the Government of Canada.
3. Tools to define metadata fields, profiles, and output file formats (notably ISO-19115 XML, FGDC, etc)
4. Of particular note, some metadata is defined as composite sets of other fields (e.g. contributors, source data, etc) 
   which must be handled well.
5. Also of note, multilingual metadata must be handled properly.
6. Tools to define datasets and their associated metadata
7. Tools to manage the workflow of approving and publishing metadata
8. Tools to submit, validate, approve, and store data files for a dataset (also with workflows)
9. Data files may have specific metadata as well (e.g. version number)
10. Logging, error notification, and job status reports from batch scripts
11. The ability to trigger jobs/tasks based on certain conditions
12. A plugin structure to extend and enhance the user management, metadata fields, workflows, file validation, etc
13. A template structure that allows organizations to re-theme and provide additional translations
14. Written in a language common to many data scientists (Python) with support for multiple SQL backends (via SQLAlchemy?)

## Status
Currently looking for feedback and additional needs/wants for the system to ensure the direction will
support the community properly. Please open issues if you have ideas or want to start a discussion. Also 
taking feedback on a name for the system. Naming goals are: available as a Python package, pithy, appropriate
for government use.

## Roadmap

Phase 1 (target for release 1.0)
- User account management
- Ability to define metadata profiles as a set of common fields
- Support for all field types except composite types (will be later release)
- Dataset and metadata management
- Plugin structure for extensions
- Support for ISO-19115 metadata and file format
- Web interface for above with multilingual support and templating support
