from threading import Thread
from flask import Flask, render_template
from tornado.ioloop import IOLoop
import pandas as pd
from bokeh.embed import server_document
from bokeh.server.server import Server
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, Select, RangeSlider
from bokeh.layouts import column
from bokeh.palettes import Category10, Category20, Turbo256


def generatePalette(num_col):
    if num_col <= 10:
        return Category10[10]
    elif num_col > 10 and num_col <= 20:
        return Category20[20]
    else:
        return Turbo256


app = Flask(__name__)


# -- scatter --

def bkapp_scatter(doc):
    p = figure()
    df = pd.DataFrame({
        'x': [1, 2, 3, 4, 5],
        'y': [3, 6, 1, 5, 2],
        'u': [10, 12, 15, 20, 25],
        'v': [3, 20, 10, 7, 14]
    })

    src = ColumnDataSource(df)

    r = p.scatter(x='x', y='y', source=src, size='u', fill_color='red', line_color=None)

    def callback_fill(attr, old, new):
        r.glyph.fill_color = new

    select_fill = Select(title="Fill Color:", value='red', options=['red', 'green'])
    select_fill.on_change('value', callback_fill)

    def callback_size(attr, old, new):
        r.glyph.size = new

    select_size = Select(title='Size By:', value='u', options=['u', 'v'])
    select_size.on_change('value', callback_size)

    doc.add_root(column(p, select_fill, select_size))


@app.route('/scatter', methods=['GET'])
def bkapp_page_scatter():
    script = server_document('http://localhost:5006/bkapp_scatter')
    return render_template("embed.html", script=script, template="Flask")


# -- bar --

def bkapp_bar(doc):
    # get the vars
    group_var = 'x'
    color_var = 'y'

    # first, subset df to only group_var and color_var
    df = pd.DataFrame({
        'x': ['a', 'b', 'a', 'a', 'b', 'a', 'a', 'b'],
        'y': ['c', 'c', 'c', 'd', 'd', 'd', 'e', 'e'],
        'z': [1, 3, 5, 8, 6, 4, 2, 9]
    })

    # remove na, then...

    # make a dummy column for counting (unique column name)
    dummy_name = group_var + '_' + color_var
    df[dummy_name] = 1

    # count frequencies
    df1 = df.groupby([group_var, color_var]).count().unstack()[dummy_name]

    # transform nested columns to the coloring var
    color_categories = sorted(list(df[color_var].unique()))
    df1.columns = color_categories

    # plot
    x = list(df1.index)
    p = figure(x_range=x)
    src = ColumnDataSource(df1)
    num_col = len(color_categories)
    colors = generatePalette(num_col)[:num_col]

    # vbar
    r = p.vbar_stack(color_categories, x=group_var, color=colors,
                    source=src, legend_label=color_categories, width=0.9)

    # range slider
    def callback(attr, old, new):
        df_subset = df[(df['z'] >= new[0]) & (df['z'] <= new[1])]
        df_count = df_subset.groupby([group_var, color_var]).count().unstack()[dummy_name]
        df_count[group_var] = df_count.index
        src.data = df_count.to_dict(orient='list')


    slider = RangeSlider(start=0, end=10, value=(1, 9), step=.1, title='z')
    slider.on_change('value', callback)

    doc.add_root(column(p, slider))


@app.route('/bar', methods=['GET'])
def bkapp_page_bar():
    script = server_document('http://localhost:5006/bkapp_bar')
    return render_template("embed.html", script=script, template="Flask")


# -- run --

def bk_worker():
    # Can't pass num_procs > 1 in this configuration. If you need to run multiple
    # processes, see e.g. flask_gunicorn_embed.py
    server = Server({'/bkapp_scatter': bkapp_scatter, '/bkapp_bar': bkapp_bar}, io_loop=IOLoop(), allow_websocket_origin=['localhost:8000', '127.0.0.1:8000'])
    server.start()
    server.io_loop.start()


Thread(target=bk_worker).start()


if __name__ == '__main__':
    app.run(port=8000)
