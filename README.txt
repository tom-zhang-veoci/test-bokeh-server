## app.py
1. Run app.py
2. Go to localhost:8000/scatter or localhost:8000/bar

## app1.py
1. create a veoci form with exactly these column names [x, y, u, v]; all NUMERIC fields; no NA's (this is a simple proof of concept with no advanced features).
2. Make plot_template and visual_template using our regular API.
3. Make a folder named "credentials" in the root directory of this project; in it, create a file called "aws.json" - its only fields being "key" and "secret".
4. Run app1.py
5. In your browser, put in this address (replace relevant fields with the actual values):
    http://127.0.0.1:8000/scatter/<objectId>/<plotTemplateId>/<visualTemplateId>?client_id=<key>&client_secret=<secret>
