# Lost and Found System 
`This is a project under Metis Winter Projects 2023-24`

## Tech Stack
![Bootstrap](https://img.shields.io/badge/bootstrap-%238511FA.svg?style=for-the-badge&logo=bootstrap&logoColor=white)
![Flask](https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white)
![HTML5](https://img.shields.io/badge/html5-%23E34F26.svg?style=for-the-badge&logo=html5&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![MongoDB](https://img.shields.io/badge/MongoDB-%234ea94b.svg?style=for-the-badge&logo=mongodb&logoColor=white)
![Google Drive](https://img.shields.io/badge/Google%20Drive-4285F4?style=for-the-badge&logo=googledrive&logoColor=white)



## For deployment:

### Video: [Youtube](https://youtu.be/GTgK3Z7tlpQ)

### Instructions:
1. Download the zip of the repository
2. Create a virtual environment and activate it (optional)
3. `pip install -r requirements.txt`
4. Go to google cloud console and make a project, get the oauth credentials
5. Go to mongodb and get a database uri.
6. Open [_config.py](./_config.py) and enter details accordingly.
7. Rename it to `config.py`
8. Run the [run_first.py](./run_first.py) file.
9. Then create two search indexes, one for lost_items_db and one for found_items_db on the mongodb site.
10. Run the [run_second](./run_second.py) file.
11. Finally, run `python main.py`