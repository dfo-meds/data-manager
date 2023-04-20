import azure.storage.fileshare as afs
from azure.identity import DefaultAzureCredential

cred = DefaultAzureCredential()
#connect_str = "https://dpaddevdata.blob.core.windows.net"
connect_str = "DefaultEndpointsProtocol=https;AccountName=dpaddevdata;AccountKey=9MTMqzyz7p/6MFFFujNgwILpE6Y5h4e7+m4LN5swornkO29bvtUJ4qDPNWaDM+JuyxhsiCpTW9LA+AStpA2f1Q==;EndpointSuffix=core.windows.net"
#connect_str = "DefaultEndpointsProtocol=https;AccountName=dpaddevdata;EndpointSuffix=core.windows.net"

client = afs.ShareClient.from_connection_string(connect_str, "geoserver")#, credential=cred)
file = client.get_file_client("workspaces/default.xml")
print(file.url)