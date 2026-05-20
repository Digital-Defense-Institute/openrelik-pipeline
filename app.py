# Copyright 2024 Digital Defense Institute
# SPDX-License-Identifier: Apache-2.0

import os
import uuid
import json
import zipfile
import tempfile
import shutil
import re
from timesketch_api_client import client as timesketch_client
import sys 

from flask import Flask, request, jsonify

from openrelik_api_client.api_client import APIClient
from openrelik_api_client.folders import FoldersAPI
from openrelik_api_client.workflows import WorkflowsAPI

# --------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------
API_KEY = os.getenv("OPENRELIK_API_KEY", "")
API_URL = os.getenv("OPENRELIK_API_URL", "")
TIMESKETCH_PASSWORD = os.getenv("TIMESKETCH_PASSWORD", "")
TIMESKETCH_URL = os.getenv("TIMESKETCH_URL", "")

# Initialize API clients
api_client = APIClient(API_URL, API_KEY)
folders_api = FoldersAPI(api_client)
workflows_api = WorkflowsAPI(api_client)

# --------------------------------------------------------------------------------
# Initialize Flask app
# --------------------------------------------------------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 * 1024  # 10GB limit
ts_client = timesketch_client.TimesketchApi(
    host_uri=TIMESKETCH_URL, username="admin", password=TIMESKETCH_PASSWORD
)


# --------------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------------        
def create_folder(folder_name):
    """
    Create a new root folder with the given folder name.
    """
    response = folders_api.create_root_folder(folder_name)
    return response


def upload_file(file_path, folder_id):
    """
    Upload a file to the specified folder.
    """
    response = api_client.upload_file(file_path, folder_id)
    return response


def create_workflow(folder_id, file_ids):
    """
    Create a new workflow in the specified folder with the given file IDs.
    Returns the workflow ID and the workflow's folder ID.
    """
    response = workflows_api.create_workflow(folder_id, file_ids)
    workflow_id = response
    workflow = workflows_api.get_workflow(folder_id, workflow_id)
    return workflow_id, workflow["folder"]["id"]


def rename_folder(folder_id, new_name):
    """
    Rename an existing folder.
    """
    return folders_api.update_folder(folder_id, {"display_name": new_name})


def rename_workflow(folder_id, workflow_id, new_name):
    """
    Rename an existing workflow.
    """
    return workflows_api.update_workflow(
        folder_id, workflow_id, {"display_name": new_name}
    )


def add_plaso_tasks_to_workflow(folder_id, workflow_id):
    """
    Add tasks to an existing workflow, including a Plaso task and a Timesketch task.
    """
    plaso_task_uuid = str(uuid.uuid4()).replace("-", "")
    timesketch_task_uuid = str(uuid.uuid4()).replace("-", "")

    workflow_spec = {
        "spec_json": json.dumps(
            {
                "workflow": {
                    "type": "chain",
                    "isRoot": True,
                    "tasks": [
                        {
                            "task_name": "openrelik-worker-plaso.tasks.log2timeline",
                            "queue_name": "openrelik-worker-plaso",
                            "display_name": "Plaso: Log2Timeline",
                            "description": "Super timelining",
                            "task_config": [
                                {
                                    "name": "artifacts",
                                    "label": "Select artifacts to parse",
                                    "description": (
                                        "Select one or more forensic artifact definitions "
                                        "from the ForensicArtifacts project. These definitions "
                                        "specify files and data relevant to digital forensic "
                                        "investigations. Only the selected artifacts will be "
                                        "parsed."
                                    ),
                                    "type": "artifacts",
                                    "required": False,
                                },
                                {
                                    "name": "parsers",
                                    "label": "Select parsers to use",
                                    "description": (
                                        "Select one or more Plaso parsers. These parsers specify "
                                        "how to interpret files and data. Only data identified by "
                                        "the selected parsers will be processed."
                                    ),
                                    "type": "autocomplete",
                                    "items": [
                                        "winreg/amcache",
                                        "sqlite/dropbox",
                                        "text/skydrive_log_v2",
                                        "winreg/ccleaner",
                                        "sqlite/twitter_android",
                                        "plist/macos_login_window_plist",
                                        "text/cri_log",
                                        "text/powershell_transcript",
                                        "winevt",
                                        "olecf/olecf_automatic_destinations",
                                        "text/viminfo",
                                        "plist/ipod_device",
                                        "czip/oxml",
                                        "plist/airport",
                                        "plist/time_machine",
                                        "wincc_sys",
                                        "text",
                                        "text/xchatscrollback",
                                        "utmpx",
                                        "jsonl/aws_cloudtrail_log",
                                        "plist/macos_install_history",
                                        "pls_recall",
                                        "plist/macos_bluetooth",
                                        "sqlite/chrome_8_history",
                                        "sqlite/hangouts_messages",
                                        "winreg/bam",
                                        "text/android_logcat",
                                        "text/setupapi",
                                        "winreg/mrulist_shell_item_list",
                                        "winreg/windows_task_cache",
                                        "winpca_dic",
                                        "winreg/mrulistex_shell_item_list",
                                        "winreg/mstsc_rdp",
                                        "winreg/microsoft_outlook_mru",
                                        "sqlite/android_calls",
                                        "sqlite/windows_push_notification",
                                        "winreg/windows_run",
                                        "text/winfirewall",
                                        "spotlight_storedb",
                                        "sqlite/safari_historydb",
                                        "text/gdrive_synclog",
                                        "esedb",
                                        "text/teamviewer_connections_incoming",
                                        "text/mac_appfirewall_log",
                                        "sqlite/ios_screentime",
                                        "winevtx",
                                        "sqlite/appusage",
                                        "text/confluence_access",
                                        "mft",
                                        "winreg/windows_version",
                                        "onedrive_log",
                                        "text/popularity_contest",
                                        "winreg/windows_services",
                                        "windefender_history",
                                        "winreg/windows_usbstor_devices",
                                        "plist/ios_identityservices",
                                        "usnjrnl",
                                        "trendmicro_vd",
                                        "prefetch",
                                        "text/aws_elb_access",
                                        "mac_keychain",
                                        "sqlite/edge_load_statistics",
                                        "filestat",
                                        "jsonl/azure_activity_log",
                                        "sqlite/android_webviewcache",
                                        "sqlite/imessage",
                                        "sqlite/chrome_17_cookies",
                                        "plist/safari_history",
                                        "msiecf",
                                        "sqlite/ios_powerlog",
                                        "sqlite/firefox_history",
                                        "locate_database",
                                        "text/snort_fastlog",
                                        "esedb/msie_webcache",
                                        "jsonl/docker_container_log",
                                        "trendmicro_url",
                                        "sqlite/mac_document_versions",
                                        "text/ios_lockdownd",
                                        "winreg/bagmru",
                                        "chrome_preferences",
                                        "sqlite/ls_quarantine",
                                        "sqlite/ios_datausage",
                                        "sqlite",
                                        "simatic_s7",
                                        "czip",
                                        "plist/macos_login_items_plist",
                                        "plist/plist_default",
                                        "winreg/mrulist_string",
                                        "sqlite/firefox_118_downloads",
                                        "text/teamviewer_application_log",
                                        "firefox_cache",
                                        "sqlite/android_webview",
                                        "winreg",
                                        "winpca_db0",
                                        "text/teamviewer_connections_outgoing",
                                        "sqlite/twitter_ios",
                                        "olecf",
                                        "bsm_log",
                                        "opera_global",
                                        "text/googlelog",
                                        "android_app_usage",
                                        "mcafee_protection",
                                        "winreg/microsoft_office_mru",
                                        "sqlite/windows_eventtranscript",
                                        "asl_log",
                                        "fish_history",
                                        "winreg/explorer_mountpoints2",
                                        "sqlite/kodi",
                                        "winreg/mrulistex_string",
                                        "winreg/networks",
                                        "text/winiis",
                                        "sqlite/android_sms",
                                        "cups_ipp",
                                        "winreg/winrar_mru",
                                        "lnk",
                                        "bencode/bencode_utorrent",
                                        "jsonl",
                                        "plist/launchd_plist",
                                        "winreg/windows_sam_users",
                                        "plist/macuser",
                                        "text/skydrive_log_v1",
                                        "text/mac_wifi",
                                        "plist/spotlight",
                                        "symantec_scanlog",
                                        "text/ios_sysdiag_log",
                                        "winreg/msie_zone",
                                        "winreg/userassist",
                                        "jsonl/ios_application_privacy",
                                        "sqlite/chrome_27_history",
                                        "text/vsftpd",
                                        "bencode/bencode_transmission",
                                        "fseventsd",
                                        "olecf/olecf_default",
                                        "jsonl/microsoft_audit_log",
                                        "unified_logging",
                                        "java_idx",
                                        "sqlite/chrome_extension_activity",
                                        "sqlite/kik_ios",
                                        "opera_typed_history",
                                        "sqlite/windows_timeline",
                                        "text/sccm",
                                        "sqlite/tango_android_profile",
                                        "sqlite/firefox_10_cookies",
                                        "sqlite/macostcc",
                                        "text/macos_launchd_log",
                                        "chrome_cache",
                                        "custom_destinations",
                                        "winreg/network_drives",
                                        "plist/ios_carplay",
                                        "olecf/olecf_summary",
                                        "sqlite/tango_android_tc",
                                        "utmp",
                                        "sqlite/chrome_autofill",
                                        "sqlite/firefox_downloads",
                                        "bodyfile",
                                        "sqlite/android_app_usage",
                                        "text/selinux",
                                        "plist/macos_software_update",
                                        "pe",
                                        "plist/apple_id",
                                        "text/syslog_traditional",
                                        "winreg/windows_boot_execute",
                                        "systemd_journal",
                                        "firefox_cache2",
                                        "text/apache_access",
                                        "plist/macos_background_items_plist",
                                        "jsonl/docker_layer_config",
                                        "winreg/windows_boot_verify",
                                        "text/ios_logd",
                                        "networkminer_fileinfo",
                                        "winreg/mrulistex_string_and_shell_item",
                                        "esedb/file_history",
                                        "sqlite/mac_notes",
                                        "sqlite/chrome_66_cookies",
                                        "text/sophos_av",
                                        "esedb/srum",
                                        "bencode",
                                        "winreg/winreg_default",
                                        "text/xchatlog",
                                        "sqlite/zeitgeist",
                                        "text/postgresql",
                                        "sqlite/firefox_2_cookies",
                                        "winreg/windows_usb_devices",
                                        "winreg/windows_timezone",
                                        "binary_cookies",
                                        "winjob",
                                        "recycle_bin_info2",
                                        "plist/safari_downloads",
                                        "sqlite/ios_netusage",
                                        "text/apt_history",
                                        "plist/spotlight_volume",
                                        "sqlite/skype",
                                        "sqlite/google_drive",
                                        "winreg/windows_typed_urls",
                                        "jsonl/docker_container_config",
                                        "text/dpkg",
                                        "text/zsh_extended_history",
                                        "text/syslog",
                                        "sqlite/mackeeper_cache",
                                        "winreg/mstsc_rdp_mru",
                                        "winreg/windows_shutdown",
                                        "olecf/olecf_document_summary",
                                        "winreg/appcompatcache",
                                        "winreg/mrulistex_string_and_shell_item_list",
                                        "text/santa",
                                        "winreg/winlogon",
                                        "text/bash_history",
                                        "text/mac_securityd",
                                        "recycle_bin",
                                        "sqlite/android_turbo",
                                        "jsonl/azure_application_gateway_access_log",
                                        "rplog",
                                        "winreg/explorer_programscache",
                                        "esedb/user_access_logging",
                                        "jsonl/gcp_log",
                                        "sqlite/mac_knowledgec",
                                        "plist/macos_startup_item_plist",
                                        "plist",
                                    ],
                                    "required": False,
                                },
                                {
                                    "name": "archives",
                                    "label": "Archives",
                                    "description": (
                                        "Select one or more Plaso archive types. "
                                        "Files inside these archive types will be processed."
                                    ),
                                    "type": "autocomplete",
                                    "items": ["iso9660", "modi", "tar", "vhdi", "zip"],
                                    "required": False,
                                },
                            ],
                            "type": "task",
                            "uuid": f"{plaso_task_uuid}",
                            "tasks": [],
                        }
                    ],
                }
            }
        )
    }

    return workflows_api.update_workflow(folder_id, workflow_id, workflow_spec)


def add_plaso_ts_tasks_to_workflow(folder_id, workflow_id, sketch_name, sketch_id, timeline_name):
    """
    Add tasks to an existing workflow, including a Plaso task and a Timesketch task.
    """
    plaso_task_uuid = str(uuid.uuid4()).replace("-", "")
    timesketch_task_uuid = str(uuid.uuid4()).replace("-", "")

    task_config = [
        {
            "name": "sketch_name",
            "label": "Create a new sketch",
            "description": "Create a new sketch",
            "type": "text",
            "required": False,
            "value": f"{sketch_name}",
        },
        {
            "name": "timeline_name",
            "label": "Name of the timeline to create",
            "description": "Timeline name",
            "type": "text",
            "required": False,
            "value": f"{timeline_name}"
        }
    ]
    if sketch_id != "":
        task_config = [
            {
                "name": "sketch_id",
                "label": "Add to existing sketch",
                "description": "Add to existing sketch",
                "type": "text",
                "required": False,
                "value": f"{sketch_id}",
            },
            {
                "name": "timeline_name",
                "label": "Name of the timeline to create",
                "description": "Timeline name",
                "type": "text",
                "required": False,
                "value": f"{timeline_name}"
            }
        ]
        
    workflow_spec = {
        "spec_json": json.dumps(
            {
                "workflow": {
                    "type": "chain",
                    "isRoot": True,
                    "tasks": [
                        {
                            "task_name": "openrelik-worker-plaso.tasks.log2timeline",
                            "queue_name": "openrelik-worker-plaso",
                            "display_name": "Plaso: Log2Timeline",
                            "description": "Super timelining",
                            "task_config": [
                                {
                                    "name": "artifacts",
                                    "label": "Select artifacts to parse",
                                    "description": (
                                        "Select one or more forensic artifact definitions "
                                        "from the ForensicArtifacts project. These definitions "
                                        "specify files and data relevant to digital forensic "
                                        "investigations. Only the selected artifacts will be "
                                        "parsed."
                                    ),
                                    "type": "artifacts",
                                    "required": False,
                                },
                                {
                                    "name": "parsers",
                                    "label": "Select parsers to use",
                                    "description": (
                                        "Select one or more Plaso parsers. These parsers specify "
                                        "how to interpret files and data. Only data identified by "
                                        "the selected parsers will be processed."
                                    ),
                                    "type": "autocomplete",
                                    "items": [
                                        "winreg/amcache",
                                        "sqlite/dropbox",
                                        "text/skydrive_log_v2",
                                        "winreg/ccleaner",
                                        "sqlite/twitter_android",
                                        "plist/macos_login_window_plist",
                                        "text/cri_log",
                                        "text/powershell_transcript",
                                        "winevt",
                                        "olecf/olecf_automatic_destinations",
                                        "text/viminfo",
                                        "plist/ipod_device",
                                        "czip/oxml",
                                        "plist/airport",
                                        "plist/time_machine",
                                        "wincc_sys",
                                        "text",
                                        "text/xchatscrollback",
                                        "utmpx",
                                        "jsonl/aws_cloudtrail_log",
                                        "plist/macos_install_history",
                                        "pls_recall",
                                        "plist/macos_bluetooth",
                                        "sqlite/chrome_8_history",
                                        "sqlite/hangouts_messages",
                                        "winreg/bam",
                                        "text/android_logcat",
                                        "text/setupapi",
                                        "winreg/mrulist_shell_item_list",
                                        "winreg/windows_task_cache",
                                        "winpca_dic",
                                        "winreg/mrulistex_shell_item_list",
                                        "winreg/mstsc_rdp",
                                        "winreg/microsoft_outlook_mru",
                                        "sqlite/android_calls",
                                        "sqlite/windows_push_notification",
                                        "winreg/windows_run",
                                        "text/winfirewall",
                                        "spotlight_storedb",
                                        "sqlite/safari_historydb",
                                        "text/gdrive_synclog",
                                        "esedb",
                                        "text/teamviewer_connections_incoming",
                                        "text/mac_appfirewall_log",
                                        "sqlite/ios_screentime",
                                        "winevtx",
                                        "sqlite/appusage",
                                        "text/confluence_access",
                                        "mft",
                                        "winreg/windows_version",
                                        "onedrive_log",
                                        "text/popularity_contest",
                                        "winreg/windows_services",
                                        "windefender_history",
                                        "winreg/windows_usbstor_devices",
                                        "plist/ios_identityservices",
                                        "usnjrnl",
                                        "trendmicro_vd",
                                        "prefetch",
                                        "text/aws_elb_access",
                                        "mac_keychain",
                                        "sqlite/edge_load_statistics",
                                        "filestat",
                                        "jsonl/azure_activity_log",
                                        "sqlite/android_webviewcache",
                                        "sqlite/imessage",
                                        "sqlite/chrome_17_cookies",
                                        "plist/safari_history",
                                        "msiecf",
                                        "sqlite/ios_powerlog",
                                        "sqlite/firefox_history",
                                        "locate_database",
                                        "text/snort_fastlog",
                                        "esedb/msie_webcache",
                                        "jsonl/docker_container_log",
                                        "trendmicro_url",
                                        "sqlite/mac_document_versions",
                                        "text/ios_lockdownd",
                                        "winreg/bagmru",
                                        "chrome_preferences",
                                        "sqlite/ls_quarantine",
                                        "sqlite/ios_datausage",
                                        "sqlite",
                                        "simatic_s7",
                                        "czip",
                                        "plist/macos_login_items_plist",
                                        "plist/plist_default",
                                        "winreg/mrulist_string",
                                        "sqlite/firefox_118_downloads",
                                        "text/teamviewer_application_log",
                                        "firefox_cache",
                                        "sqlite/android_webview",
                                        "winreg",
                                        "winpca_db0",
                                        "text/teamviewer_connections_outgoing",
                                        "sqlite/twitter_ios",
                                        "olecf",
                                        "bsm_log",
                                        "opera_global",
                                        "text/googlelog",
                                        "android_app_usage",
                                        "mcafee_protection",
                                        "winreg/microsoft_office_mru",
                                        "sqlite/windows_eventtranscript",
                                        "asl_log",
                                        "fish_history",
                                        "winreg/explorer_mountpoints2",
                                        "sqlite/kodi",
                                        "winreg/mrulistex_string",
                                        "winreg/networks",
                                        "text/winiis",
                                        "sqlite/android_sms",
                                        "cups_ipp",
                                        "winreg/winrar_mru",
                                        "lnk",
                                        "bencode/bencode_utorrent",
                                        "jsonl",
                                        "plist/launchd_plist",
                                        "winreg/windows_sam_users",
                                        "plist/macuser",
                                        "text/skydrive_log_v1",
                                        "text/mac_wifi",
                                        "plist/spotlight",
                                        "symantec_scanlog",
                                        "text/ios_sysdiag_log",
                                        "winreg/msie_zone",
                                        "winreg/userassist",
                                        "jsonl/ios_application_privacy",
                                        "sqlite/chrome_27_history",
                                        "text/vsftpd",
                                        "bencode/bencode_transmission",
                                        "fseventsd",
                                        "olecf/olecf_default",
                                        "jsonl/microsoft_audit_log",
                                        "unified_logging",
                                        "java_idx",
                                        "sqlite/chrome_extension_activity",
                                        "sqlite/kik_ios",
                                        "opera_typed_history",
                                        "sqlite/windows_timeline",
                                        "text/sccm",
                                        "sqlite/tango_android_profile",
                                        "sqlite/firefox_10_cookies",
                                        "sqlite/macostcc",
                                        "text/macos_launchd_log",
                                        "chrome_cache",
                                        "custom_destinations",
                                        "winreg/network_drives",
                                        "plist/ios_carplay",
                                        "olecf/olecf_summary",
                                        "sqlite/tango_android_tc",
                                        "utmp",
                                        "sqlite/chrome_autofill",
                                        "sqlite/firefox_downloads",
                                        "bodyfile",
                                        "sqlite/android_app_usage",
                                        "text/selinux",
                                        "plist/macos_software_update",
                                        "pe",
                                        "plist/apple_id",
                                        "text/syslog_traditional",
                                        "winreg/windows_boot_execute",
                                        "systemd_journal",
                                        "firefox_cache2",
                                        "text/apache_access",
                                        "plist/macos_background_items_plist",
                                        "jsonl/docker_layer_config",
                                        "winreg/windows_boot_verify",
                                        "text/ios_logd",
                                        "networkminer_fileinfo",
                                        "winreg/mrulistex_string_and_shell_item",
                                        "esedb/file_history",
                                        "sqlite/mac_notes",
                                        "sqlite/chrome_66_cookies",
                                        "text/sophos_av",
                                        "esedb/srum",
                                        "bencode",
                                        "winreg/winreg_default",
                                        "text/xchatlog",
                                        "sqlite/zeitgeist",
                                        "text/postgresql",
                                        "sqlite/firefox_2_cookies",
                                        "winreg/windows_usb_devices",
                                        "winreg/windows_timezone",
                                        "binary_cookies",
                                        "winjob",
                                        "recycle_bin_info2",
                                        "plist/safari_downloads",
                                        "sqlite/ios_netusage",
                                        "text/apt_history",
                                        "plist/spotlight_volume",
                                        "sqlite/skype",
                                        "sqlite/google_drive",
                                        "winreg/windows_typed_urls",
                                        "jsonl/docker_container_config",
                                        "text/dpkg",
                                        "text/zsh_extended_history",
                                        "text/syslog",
                                        "sqlite/mackeeper_cache",
                                        "winreg/mstsc_rdp_mru",
                                        "winreg/windows_shutdown",
                                        "olecf/olecf_document_summary",
                                        "winreg/appcompatcache",
                                        "winreg/mrulistex_string_and_shell_item_list",
                                        "text/santa",
                                        "winreg/winlogon",
                                        "text/bash_history",
                                        "text/mac_securityd",
                                        "recycle_bin",
                                        "sqlite/android_turbo",
                                        "jsonl/azure_application_gateway_access_log",
                                        "rplog",
                                        "winreg/explorer_programscache",
                                        "esedb/user_access_logging",
                                        "jsonl/gcp_log",
                                        "sqlite/mac_knowledgec",
                                        "plist/macos_startup_item_plist",
                                        "plist",
                                    ],
                                    "required": False,
                                },
                                {
                                    "name": "archives",
                                    "label": "Archives",
                                    "description": (
                                        "Select one or more Plaso archive types. "
                                        "Files inside these archive types will be processed."
                                    ),
                                    "type": "autocomplete",
                                    "items": ["iso9660", "modi", "tar", "vhdi", "zip"],
                                    "required": False,
                                },
                            ],
                            "type": "task",
                            "uuid": f"{plaso_task_uuid}",
                            "tasks": [
                                {
                                    "task_name": "openrelik-worker-timesketch.tasks.upload",
                                    "queue_name": "openrelik-worker-timesketch",
                                    "display_name": "Upload to Timesketch",
                                    "description": "Upload resulting file to Timesketch",
                                    "task_config": task_config,
                                    "type": "task",
                                    "uuid": f"{timesketch_task_uuid}",
                                    "tasks": [],
                                }
                            ],
                        }
                    ],
                }
            }
        )
    }

    return workflows_api.update_workflow(folder_id, workflow_id, workflow_spec)


def add_hayabusa_tasks_to_workflow(folder_id, workflow_id):
    """
    Add tasks to an existing workflow, including a Plaso task and a Timesketch task.
    """
    hayabusa_task_uuid = str(uuid.uuid4()).replace("-", "")
    timesketch_task_uuid = str(uuid.uuid4()).replace("-", "")

    workflow_spec = {
        "spec_json": json.dumps(
            {
                "workflow": {
                    "type": "chain",
                    "isRoot": True,
                    "tasks": [
                        {
                            "task_name": "openrelik-worker-hayabusa.tasks.csv_timeline",
                            "queue_name": "openrelik-worker-hayabusa",
                            "display_name": "Hayabusa CSV timeline",
                            "description": "Windows event log triage",
                            "type": "task",
                            "uuid": f"{hayabusa_task_uuid}",
                            "tasks": [],
                        }
                    ],
                }
            }
        )
    }

    return workflows_api.update_workflow(folder_id, workflow_id, workflow_spec)


def add_hayabusa_ts_tasks_to_workflow(folder_id, workflow_id, sketch_name, sketch_id, timeline_name):
    """
    Add tasks to an existing workflow, including a Plaso task and a Timesketch task.
    """
    hayabusa_task_uuid = str(uuid.uuid4()).replace("-", "")
    timesketch_task_uuid = str(uuid.uuid4()).replace("-", "")

    task_config = [
        {
            "name": "sketch_name",
            "label": "Create a new sketch",
            "description": "Create a new sketch",
            "type": "text",
            "required": False,
            "value": f"{sketch_name}",
        },
        {
            "name": "timeline_name",
            "label": "Name of the timeline to create",
            "description": "Timeline name",
            "type": "text",
            "required": False,
            "value": f"{timeline_name}"
        }
    ]
    if sketch_id != "":
        task_config = [
            {
                "name": "sketch_id",
                "label": "Add to existing sketch",
                "description": "Add to existing sketch",
                "type": "text",
                "required": False,
                "value": f"{sketch_id}",
            },
            {
                "name": "timeline_name",
                "label": "Name of the timeline to create",
                "description": "Timeline name",
                "type": "text",
                "required": False,
                "value": f"{timeline_name}"
            }
        ]

    workflow_spec = {
        "spec_json": json.dumps(
            {
                "workflow": {
                    "type": "chain",
                    "isRoot": True,
                    "tasks": [
                        {
                            "task_name": "openrelik-worker-hayabusa.tasks.csv_timeline",
                            "queue_name": "openrelik-worker-hayabusa",
                            "display_name": "Hayabusa CSV timeline",
                            "description": "Windows event log triage",
                            "type": "task",
                            "uuid": f"{hayabusa_task_uuid}",
                            "tasks": [
                                {
                                    "task_name": "openrelik-worker-timesketch.tasks.upload",
                                    "queue_name": "openrelik-worker-timesketch",
                                    "display_name": "Upload to Timesketch",
                                    "description": "Upload resulting file to Timesketch",
                                    "task_config": task_config,
                                    "type": "task",
                                    "uuid": f"{timesketch_task_uuid}",
                                    "tasks": [],
                                }
                            ],
                        }
                    ],
                }
            }
        )
    }

    return workflows_api.update_workflow(folder_id, workflow_id, workflow_spec)


def add_hayabusa_extract_tasks_to_workflow(folder_id, workflow_id):
    """
    Add tasks to an existing workflow, including a Plaso task and a Timesketch task.
    """
    hayabusa_task_uuid = str(uuid.uuid4()).replace("-", "")
    extraction_task_uuid = str(uuid.uuid4()).replace("-", "")

    workflow_spec = {
        "spec_json": json.dumps(
            {
                "workflow": {
                    "type": "chain",
                    "isRoot": True,
                    "tasks": [
                        {
                            "task_name": "openrelik-worker-extraction.tasks.extract_archive",
                            "queue_name": "openrelik-worker-extraction",
                            "display_name": "Extract Archives",
                            "description": "Extract different types of archives",
                            "task_config": [
                                {
                                    "name": "file_filter",
                                    "label": "Select files (glob patterns) to extract",
                                    "description": "A comma separated list of filenames to extract. Glob patterns are supported. Example: *.txt, *.evtx",
                                    "type": "text",
                                    "required": True,
                                    "value": "*.evtx",
                                }
                            ],
                            "type": "task",
                            "uuid": f"{extraction_task_uuid}",
                            "tasks": [
                                {
                                    "task_name": "openrelik-worker-hayabusa.tasks.csv_timeline",
                                    "queue_name": "openrelik-worker-hayabusa",
                                    "display_name": "Hayabusa CSV timeline",
                                    "description": "Windows event log triage",
                                    "type": "task",
                                    "uuid": f"{hayabusa_task_uuid}",
                                    "tasks": [],
                                }
                            ],
                        }
                    ],
                }
            }
        )
    }

    return workflows_api.update_workflow(folder_id, workflow_id, workflow_spec)


def add_hayabusa_extract_ts_tasks_to_workflow(folder_id, workflow_id, sketch_name, sketch_id, timeline_name):
    """
    Add tasks to an existing workflow, including a Plaso task and a Timesketch task.
    """
    hayabusa_task_uuid = str(uuid.uuid4()).replace("-", "")
    timesketch_task_uuid = str(uuid.uuid4()).replace("-", "")
    extraction_task_uuid = str(uuid.uuid4()).replace("-", "")

    task_config = [
        {
            "name": "sketch_name",
            "label": "Create a new sketch",
            "description": "Create a new sketch",
            "type": "text",
            "required": False,
            "value": f"{sketch_name}",
        }
    ]
    if sketch_id != "":
        task_config = [
            {
                "name": "sketch_id",
                "label": "Add to existing sketch",
                "description": "Add to existing sketch",
                "type": "text",
                "required": False,
                "value": f"{sketch_id}",
            }
        ]

    workflow_spec = {
        "spec_json": json.dumps(
            {
                "workflow": {
                    "type": "chain",
                    "isRoot": True,
                    "tasks": [
                        {
                            "task_name": "openrelik-worker-extraction.tasks.extract_archive",
                            "queue_name": "openrelik-worker-extraction",
                            "display_name": "Extract Archives",
                            "description": "Extract different types of archives",
                            "task_config": [
                                {
                                    "name": "file_filter",
                                    "label": "Select files (glob patterns) to extract",
                                    "description": "A comma separated list of filenames to extract. Glob patterns are supported. Example: *.txt, *.evtx",
                                    "type": "text",
                                    "required": True,
                                    "value": "*.evtx",
                                }
                            ],
                            "type": "task",
                            "uuid": f"{extraction_task_uuid}",
                            "tasks": [
                                {
                                    "task_name": "openrelik-worker-hayabusa.tasks.csv_timeline",
                                    "queue_name": "openrelik-worker-hayabusa",
                                    "display_name": "Hayabusa CSV timeline",
                                    "description": "Windows event log triage",
                                    "type": "task",
                                    "uuid": f"{hayabusa_task_uuid}",
                                    "tasks": [
                                        {
                                            "task_name": "openrelik-worker-timesketch.tasks.upload",
                                            "queue_name": "openrelik-worker-timesketch",
                                            "display_name": "Upload to Timesketch",
                                            "description": "Upload resulting file to Timesketch",
                                            "task_config": task_config,
                                            "type": "task",
                                            "uuid": f"{timesketch_task_uuid}",
                                            "tasks": [],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            }
        )
    }

    return workflows_api.update_workflow(folder_id, workflow_id, workflow_spec)


def run_workflow(folder_id, workflow_id):
    """
    Trigger the workflow execution.
    """
    return workflows_api.run_workflow(folder_id, workflow_id)


def extract_fqdn_and_label(filename):
    # Check if the filename starts with "vr_kapefiles"
    if filename.startswith("vr_kapefiles"):
        # vr_kapefiles_<fqdn>_<label>.zip
        pattern = r"^vr_kapefiles_([^_]+)_(.+)\.zip$"
        match = re.match(pattern, filename)
        if match:
            fqdn = match.group(1)
            label = match.group(2)
            return fqdn, label
    
    return None, None


# --------------------------------------------------------------------------------
# Error handlers
# --------------------------------------------------------------------------------
@app.errorhandler(400)
def bad_request(error):
    """
    Return a 400 error for a Bad Request.
    """
    return "Bad Request!", 400


@app.errorhandler(401)
def unauthorized(error):
    """
    Return a 401 error for an Unauthorized request.
    """
    return "Unauthorized!", 401


@app.errorhandler(403)
def forbidden(error):
    """
    Return a 403 error for a Forbidden request.
    """
    return "Forbidden!", 403


@app.errorhandler(404)
def page_not_found(error):
    """
    Return a 404 error for a Page Not Found.
    """
    return "Page Not Found!", 404


@app.errorhandler(405)
def method_not_allowed(error):
    """
    Return a 405 error for Method Not Allowed.
    """
    return "Method Not Allowed!", 405


@app.errorhandler(413)
def request_entity_too_large(error):
    """
    Return a 413 error if the file or payload exceeds the maximum allowed size.
    """
    return "File is too large!", 413


@app.errorhandler(500)
def internal_server_error(error):
    """
    Return a 500 error for Internal Server Error.
    """
    return "Internal Server Error!", 500


@app.errorhandler(503)
def service_unavailable(error):
    """
    Return a 503 error for Service Unavailable.
    """
    return "Service Unavailable!", 503


# --------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------
@app.route("/api/hayabusa/timesketch", methods=["POST"])
def api_hayabusa_timesketch():
    """
    Endpoint to handle file uploads, create a workflow, and run it.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    filename = file.filename
    timeline_name, extension = os.path.splitext(filename)
    file_path = os.path.join("/tmp", filename)
    file.save(file_path)
    fqdn, label = extract_fqdn_and_label(filename)

    # If a label is part of the filename, check to see if sketch exists with the same name and add it to it instead of creating a new sketch
    sketch_id = ""
    if fqdn and label and label != "Null":
        sketch_name = label
        timeline_name = fqdn
    else:
        sketch_name = filename

    try:
        sketches = ts_client.list_sketches()
        for sketch in sketches:
            if sketch.name == sketch_name:
                sketch_id = sketch.id
    except Exception as e:
        print("Error communicating with timesketch API: %s" % (e))

    folder_id = create_folder(f"{filename} Hayabusa Timelines")
    file_id = upload_file(file_path, folder_id)
    workflow_id, workflow_folder_id = create_workflow(folder_id, [file_id])

    rename_folder(
        workflow_folder_id, f"{filename} Hayabusa to Timesketch Workflow Folder"
    )
    rename_workflow(
        folder_id, workflow_id, f"{filename} Hayabusa to Timesketch Workflow"
    )

    if zipfile.is_zipfile(file_path):
        add_hayabusa_extract_ts_tasks_to_workflow(folder_id, workflow_id, sketch_name, sketch_id, timeline_name)
    else:
        add_hayabusa_ts_tasks_to_workflow(folder_id, workflow_id, sketch_name, sketch_id, timeline_name)
    run = run_workflow(folder_id, workflow_id)

    return jsonify(
        {
            "message": "Hayabusa to Timesketch Workflow(s) started successfully",
        }
    )


@app.route("/api/hayabusa", methods=["POST"])
def api_hayabusa():
    """
    Endpoint to handle file uploads, create a workflow, and run it.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    filename = file.filename

    file_path = os.path.join("/tmp", filename)
    file.save(file_path)

    folder_id = create_folder(f"{filename} Hayabusa Timelines")
    file_id = upload_file(file_path, folder_id)
    workflow_id, workflow_folder_id = create_workflow(folder_id, [file_id])

    rename_folder(workflow_folder_id, f"{filename} Hayabusa Workflow Folder")
    rename_workflow(folder_id, workflow_id, f"{filename} Hayabusa Workflow")

    if zipfile.is_zipfile(file_path):
        add_hayabusa_extract_tasks_to_workflow(folder_id, workflow_id, filename)
    else:
        add_hayabusa_tasks_to_workflow(folder_id, workflow_id)
    run = run_workflow(folder_id, workflow_id)

    return jsonify(
        {
            "message": "Hayabusa Workflow(s) started successfully",
        }
    )


@app.route("/api/plaso/timesketch", methods=["POST"])
def api_plaso_timesketch():
    """
    Endpoint to handle file uploads, create a workflow, and run it.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    filename = file.filename
    timeline_name, extension = os.path.splitext(filename)
    fqdn, label = extract_fqdn_and_label(filename)

    # If a label is part of the filename, check to see if sketch exists with the same name and add it to it instead of creating a new sketch
    sketch_id = ""
    if fqdn and label and label != "Null":
        sketch_name = label
        timeline_name = fqdn
    else:
        sketch_name = filename

    try:
        sketches = ts_client.list_sketches()
        for sketch in sketches:
            if sketch.name == sketch_name:
                sketch_id = sketch.id
    except Exception as e:
        print("Error communicating with timesketch API: %s" % (e))

    file_path = os.path.join("/tmp", filename)
    file.save(file_path)

    folder_id = create_folder(f"{filename} Plaso Timeline")
    file_id = upload_file(file_path, folder_id)
    workflow_id, workflow_folder_id = create_workflow(folder_id, [file_id])

    rename_folder(workflow_folder_id, f"{filename} Plaso to Timesketch Workflow Folder")
    rename_workflow(folder_id, workflow_id, f"{filename} Plaso to Timesketch Workflow")

    add_plaso_ts_tasks_to_workflow(folder_id, workflow_id, sketch_name, sketch_id, timeline_name)
    run = run_workflow(folder_id, workflow_id)

    return jsonify(
        {
            "message": "Plaso to Timesketch Workflow started successfully",
            "workflow_id": workflow_id,
            "run_details": run,
        }
    )


@app.route("/api/plaso", methods=["POST"])
def api_plaso():
    """
    Endpoint to handle file uploads, create a workflow, and run it.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    filename = file.filename

    file_path = os.path.join("/tmp", filename)
    file.save(file_path)

    folder_id = create_folder(f"{filename} Plaso Timeline")
    file_id = upload_file(file_path, folder_id)
    workflow_id, workflow_folder_id = create_workflow(folder_id, [file_id])

    rename_folder(workflow_folder_id, f"{filename} Plaso Workflow Folder")
    rename_workflow(folder_id, workflow_id, f"{filename} Plaso Workflow")

    add_plaso_tasks_to_workflow(folder_id, workflow_id)
    run = run_workflow(folder_id, workflow_id)

    return jsonify(
        {
            "message": "Plaso Workflow started successfully",
            "workflow_id": workflow_id,
            "run_details": run,
        }
    )


# --------------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="localhost", debug=True)
