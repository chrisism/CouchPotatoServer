from .main import Downloader


def autoload():
    return Downloader()


config = [{ 
    'name': 'download_basics',
    'tab': 'downloaders',
    'order': 20,
    'groups': [
         {
            'label': 'Wake on Download',
            'description': 'Wake up a machine before downloading',
            'name': 'wake_on_download',
            'tab': 'downloaders',
            'options': [
                {
                    'name': 'wake_enabled',
                    'default': 0,
                    'type': 'enabler',
                },
                {
                    'name': 'mac_address',
                    'label': 'MAC address',
                }
            ],
        }
        ]
    }, {
    'name': 'download_providers',
    'groups': [       
        {
            'label': 'Downloaders',
            'description': 'You can select different downloaders for each type (usenet / torrent)',
            'type': 'list',
            'name': 'download_providers',
            'tab': 'downloaders',
            'options': [],
        },
    ],
}]
