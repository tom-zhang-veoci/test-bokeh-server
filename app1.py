from threading import Thread
from flask import Flask, render_template
from tornado.ioloop import IOLoop
import pandas as pd
from bokeh.embed import server_document
from bokeh.server.server import Server
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, Select
from bokeh.layouts import column
from bokeh.palettes import Category10, Category20, Turbo256
from flask_restful import reqparse, abort
from http import HTTPStatus
import boto3
from pathlib import Path
import json
import requests


def generatePalette(num_col):
    if num_col <= 10:
        return Category10[10]
    elif num_col > 10 and num_col <= 20:
        return Category20[20]
    else:
        return Turbo256


# param parser
params = reqparse.RequestParser()
params.add_argument('client_id', type=str,
                    help='client_id is required', required=True)
params.add_argument('client_secret', type=str,
                    help='client_secret is required', required=True)
params.add_argument('output_type', type=str,
                    help='html | json', default='json')


# db
base_path = Path(__file__).parent
# print(base_path)
file_path = (base_path / "credentials/aws.json").resolve()
f = open(file_path, "r")
# Get credentials (JSON file)
aws_json = json.loads(f.read())
# Initialize a DynamoDb Client
session = boto3.Session(aws_access_key_id=aws_json['key'],
                        aws_secret_access_key=aws_json['secret'], region_name='us-east-1')
dynamodb = session.resource('dynamodb')

plot_config_table = dynamodb.Table('PlotTemplates')
visual_config_table = dynamodb.Table('VisualTemplates')


app = Flask(__name__)


@app.route('/scatter/<string:objectId>/<string:plotTemplateId>/<string:visualTemplateId>', methods=['GET'])
def bkapp_page_scatter(objectId, plotTemplateId, visualTemplateId):

    # validate request parameter inputs
    args = params.parse_args()

    # retrive the desired item from both tables
    resp = dynamodb.batch_get_item(
        RequestItems={
            'PlotTemplates': {
                'Keys': [
                    {
                        'object_id': objectId,
                        'plot_id': plotTemplateId
                    }
                ],
                'ConsistentRead': True
            },
            'VisualTemplates': {
                'Keys': [
                    {
                        'object_id': objectId,
                        'visual_id': visualTemplateId
                    }
                ]
            }
        },
        ReturnConsumedCapacity='TOTAL'
    )

    resp = resp['Responses']

    # validations

    # if some template is not found
    if len(resp['PlotTemplates']) > 0 and len(resp['VisualTemplates']) == 0:
        abort(HTTPStatus.BAD_REQUEST,
              message='Valid plotTemplateId but invalid visualTemplateId for this objectId; you should create a new visual template.')
    elif len(resp['PlotTemplates']) == 0 and len(resp['VisualTemplates']) > 0:
        abort(HTTPStatus.BAD_REQUEST, message='Invalid plotTemplateId but valid visualTemplateId for this objectId; you should call /PATCH to associate the visual template with a new plot template.')
    elif len(resp['PlotTemplates']) == 0 and len(resp['VisualTemplates']) == 0:
        abort(HTTPStatus.NOT_FOUND,
              message='Both plotTemplateId and visualTemplateId are invalid for this objectId.')

    # if reached here, then we have both templates
    plot_template = resp['PlotTemplates'][0]
    visual_template = resp['VisualTemplates'][0]

    # TODO? serializing both templates is optional? because fields of interest are all strings, and I'm not returning the items

    # make sure plot_id's and container_id's match in both templates
    if plot_template['plot_id'] != visual_template['plot_template_id']:
        abort(HTTPStatus.BAD_REQUEST,
              message="plot_id's in plot template and visual template do not match.")

    if plot_template['container_id'] != visual_template['container_id']:
        abort(HTTPStatus.BAD_REQUEST,
              message="container_id's in plot template and visual template do not match.")

    # retrive access token
    BASE = 'https://stage.veoci.com/api/v2/'

    try:
        tok_req = requests.post(BASE + 'oauth/token',
                                params={'grant_type': 'client_credentials',
                                        'client_id': args['client_id'],
                                        'client_secret': args['client_secret']})
    except requests.exceptions.RequestException:
        abort(500, message='Access token request failed.')

    tok_req = tok_req.json()

    try:
        access_token = tok_req['access_token']
    except KeyError:
        abort(HTTPStatus.UNAUTHORIZED,
              message='Could not get access token; invalid credentials specified.')

    # get form entries
    BASE1 = 'https://stage.veoci.com/api/v1/'
    # format = 'https://stage.veoci.com/veoci/api/<containerId>/forms/<formId>/entries/'
    try:
        entries_req = requests.get(BASE1 + str(plot_template['container_id']) + '/forms/' + str(objectId) + '/entries/',
                                   headers={'Authorization': 'Bearer ' + access_token})
    except requests.exceptions.RequestException:
        abort(HTTPStatus.INTERNAL_SERVER_ERROR,
              message='Get form entries failed.')

    try:
        entries_req = entries_req.json()
    except ValueError:  # this means did not get a result
        abort(HTTPStatus.BAD_REQUEST,
              message='Could not get form entries; invalid formId and/or containerId specified.')

    # extract fields info
    fields = entries_req['fields']
    fields = pd.DataFrame(fields)
    fields = fields[['fieldId', 'name', 'type']]

    # extract entries data
    entries = entries_req['entries']
    entries = pd.DataFrame(entries)['values']
    df = pd.DataFrame(entries.to_list())
    df.columns = fields['name']








    # -- bokeh server stuff --

    df['x'] = df['x'].apply(float)
    df['y'] = df['y'].apply(float)
    df['u'] = df['u'].apply(float)
    df['v'] = df['v'].apply(float)


    def bkapp_scatter(doc):
        p = figure()

        src = ColumnDataSource(df)

        r = p.scatter(x='x', y='y', source=src, size='u',
                      fill_color='red', line_color=None)

        def callback_fill(attr, old, new):
            r.glyph.fill_color = new

        select_fill = Select(title="Fill Color:", value='red',
                             options=['red', 'green'])
        select_fill.on_change('value', callback_fill)

        def callback_size(attr, old, new):
            r.glyph.size = new

        select_size = Select(title='Size By:', value='u', options=['u', 'v'])
        select_size.on_change('value', callback_size)

        doc.add_root(column(p, select_fill, select_size))


    def bk_worker():
        # Can't pass num_procs > 1 in this configuration. If you need to run multiple
        # processes, see e.g. flask_gunicorn_embed.py
        server = Server({'/bkapp_scatter': bkapp_scatter}, io_loop=IOLoop(),
                        allow_websocket_origin=['localhost:8000', '127.0.0.1:8000'])
        server.start()
        server.io_loop.start()


    Thread(target=bk_worker).start()


    script = server_document('http://localhost:5006/bkapp_scatter')
    return render_template("embed.html", script=script, template="Flask")


if __name__ == '__main__':
    app.run(port=8000)
