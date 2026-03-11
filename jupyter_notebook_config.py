# Modern Jupyter Server Config for Notebook 7
c = get_config()

# Networking (Single source of truth)
c.ServerApp.ip = '127.0.0.1'
c.ServerApp.port = 8890
c.ServerApp.open_browser = False

# Security (Modern IdentityProvider)
c.IdentityProvider.token = ''
c.ServerApp.password = ''
c.ServerApp.disable_check_xsrf = True

# UI Extensions
c.ServerApp.jpserver_extensions = {
    'notebook': True,
    'jupyterlab': True,
    'jupyter_server_terminals': True,
    'jupyter_lsp': False,
    'notebook_shim': True
}

# Logging
c.ServerApp.log_level = 'INFO'
