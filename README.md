# Lost and Found System 
`This is a project under Metis Winter Projects 2023-24`

## For deployment:
1. Download the zip of the repository
2. Create a virtual environment and activate it (optional)
3. `pip install -r requirements.txt`
4. Go to google cloud console and make a project, get the oauth credentials
5. Go to mongodb and get a database uri.
6. Open [_config.py](./_config.py) and enter details accordingly.
7. Run the [first_time.py](./first_time.py) file.
8. Then create two search indexes, one for lost_items_db and one for found_items_db on the mongodb site
9. Finally, run `python main.py`