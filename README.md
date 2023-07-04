# Science Metadata Form

This tool aims to provide a comprehensive web application for managing metadata for scientific datasets. It is a work
in progress.

## Overview

- Web-based entry forms for metadata
- Support for multilingual text fields 
- Support multiple profiles and formats in a manner that unifies metadata fields
- Approval tracking
- Automated deployment of approved changes to other systems (e.g. ERDDAP, CKAN, etc)
- Plugin support for user extensions

## Current Output Formats
- ISO 19115-3 XML
- ISO 19139 XML
- NetCDF (NCML and CDL)
- MCF YAML
- ERDDAP Dataset XML


## Current Profiles
- ISO-19115
- NetCDF ACDD 1.3 and CF 1.10
- HNAP (Government of Canada)
- CIOOS v2

## Other Cool Features
- Fully translatable user interface
- Integrated translation mechanism via Google translate or manual download/upload. 
- Workflows for new datasets and for publishing updates which can include both user approvals and automated publishing steps
- Microsoft Secure Authentication Library (MSAL) integration
- Import metadata from NetCDF or MCF YAML files

## Roadmap
- Splitting the package into GoC/CNODC required features and generic features so the generic features can be published
- 