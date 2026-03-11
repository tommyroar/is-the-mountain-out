# Jupyter Server Config for Mountain Classifier
c = get_config()

# Networking
c.ServerApp.ip = '127.0.0.1'
c.ServerApp.port = 8890
c.ServerApp.open_browser = False

# Security
c.ServerApp.token = ''
c.ServerApp.password = ''
c.ServerApp.disable_check_xsrf = True

# Performance / Stability: Disable problematic extensions
c.ServerApp.jpserver_extensions = {
    'notebook': True,
    'jupyter_lsp': False,
    'notebook_shim': False,
    'jupyterlab': False,
    'jupyter_server_terminals': False
}

# Logging
c.ServerApp.log_level = 'INFO'
