# MSAL Integration

This integration with MSAL uses the Authorization code flow to grant access.

To integrate with Microsoft Secure Authentication Library, you will need to take the following steps:

1. In Azure Portal, go to Azure Active Directory and select App registrations.
2. Create a new application. The redirect URL will be `{APPLICATION_ROOT}/api/login-from-redirect`.
3. If you wish to use a client secret or a certificate to authenticate requests, create one now.  
4. If you wish to use managed identity to authenticate, make sure you grant the machines that will be used
   to run and test the application access.
5. You will need to note the client ID (from the Overview paeg of your application) and the authority. For 
   the authority, you can click on the Endpoints link and use the WS-Federation endpoint without the "/wsfed"
   at the end.
6. If you wish to assign users to groups or organizations, you can do so by creating App Roles. The value should be 
   `group.{GROUP_NAME}` to assign the user to a group and `organization.{ORGANIZATION_SHORT_NAME}` for organizations.
   Note that if you specify a group, it will overwrite all other groups assigned to the user on login. Likewise,
   if you assign an organization, it will overwrite all other organizations on login. Specifying only groups does
   not overwrite organizations and vice versa.
7. The scopes necessary are just `email`. This is typically available by default.
8. Next, you will need to configure your application to support MSAL:

```toml
[pipeman.authentication.handlers]
# Add Azure Authentication to the list of login options
azure = "pipeman.builtins.auth_msal.controller.AzureAuthenticationHandler"

[pipeman.auth.msal]
# required
client_id = ''
authority = ''

# for client secrets method
client_secret = ''

# for certificate
thumbprint = ''
private_key = '/path/to/certificate/file'

# for managed identity
# not supported

# optional configuration
prompt = ''  # Defaults to empty (no prompt sent). Can be a comma-delimited set of values from `none` (never login the user), `login` (always reauthenticate the user), `consent` (always reobtain consent), or `select_account` (always re-select the account).
domain_hint = ''  # Either 'consumers', 'organization', or tenant domain (skips checking the domain for login purposes)
max_age = ''  # Max elapsed time since last active authentication (in seconds)
scopes = ['email'] # Can add more scopes but default only requires the email address (preferred_username and name are also checked and used if present)
app_name = 'pipeman'  # name sent to logging on Microsoft's side
app_version = '{CURRENT_VERSION}'

```