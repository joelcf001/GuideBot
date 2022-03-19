# guide.py
"""guide.py
Provides essential functions to treat and compute graphs from OpenStreetMaps"""
# author: Joel Castaño Fernandez

import osmnx as ox
import networkx as nx
from staticmap import StaticMap, CircleMarker, Line
from haversine import haversine


class SameLocationError(Exception):
    """Exception for same location situations"""
    pass


def download_graph(place):
    """Downloads and creates a networkx graph from OSM data
        Args:
            place: string
        Returns:
            networkx-based graph from place
    """

    graph = ox.graph_from_place(place, network_type='drive', simplify=True)
    ox.geo_utils.add_edge_bearings(graph)
    return graph


def save_graph(graph, filename):
    """Saves graph in pickle format in filename

    Args:
        graph: networkx-based graph
        filename: string
    """
    nx.write_gpickle(graph, filename)


def load_graph(filename):
    """Loads graph in pickle format from filename

    Args:
        filename: string
    """
    return nx.read_gpickle(filename)


def print_graph(graph):
    """Prints all nodes and edges from graph, including it's attributes

    Args:
        graph: networkx-based graph
    """

    for node, nodeinfo in graph.nodes.items():
        print(node, nodeinfo)

        for nbr, nbrinfo in graph[node].items():
            print('    ', nbr)
            edge = nbrinfo[0]  # Evitem multigraf seleccionant 1 aresta
            if 'geometry' in edge:
                del(edge['geometry'])
            print('        ', edge)


def get_directions(graph, source_location, destination_location):
    """Computes the shortest path from source_location to destination_location
       and returns a dictionary with basic information of every edge of the
       shortest path

    Args
        graph: networkx-based graph
        source_location = (lat,lon) coordinates
        destination_location = (lat,lon) coordinates
    """

    s = ox.get_nearest_node(graph, source_location)
    t = ox.get_nearest_node(graph, destination_location)
    route = nx.shortest_path(graph, s, t)

    # If current location is too close to destination location, we asume
    # user is in the same place
    if s == t and haversine(source_location,
                            destination_location, unit='m') < 100:
        raise SameLocationError

    directions = [{'angle':        graph.edges[mid, dst, 0].get('bearing') -
                   graph.edges[src, mid, 0].get('bearing'),
                   'current_name': graph.edges[src, mid, 0].get('name'),
                   'dst':         (graph.nodes[dst]['y'],
                                   graph.nodes[dst]['x']),
                   'length':       graph.edges[src, mid, 0].get('length'),
                   'mid':         (graph.nodes[mid]['y'],
                                   graph.nodes[mid]['x']),
                   'next_name':    graph.edges[mid, dst, 0].get('name'),
                   'src':         (graph.nodes[src]['y'],
                                   graph.nodes[src]['x'])}
                  for src, mid, dst in zip(route, route[1:], route[2:])]

    # If route only has two nodes, as we have a triple zip loop, directions
    # list will be empty, we add this edge
    if len(route) == 2:
        src = route[0]
        mid = route[1]
        directions.append(
            {'angle':       None,
             'current_name': graph.edges[src, mid, 0].get('name'),
             'dst':         destination_location,
             'length':       graph.edges[src, mid, 0].get('length'),
             'mid':         (graph.nodes[mid]['y'], graph.nodes[mid]['x']),
             'next_name':   None,
             'src':         (graph.nodes[src]['y'], graph.nodes[src]['x'])}
        )

    # Adds the dictionaries related to the destination_location coordinates
    directions.extend([
        {'angle':        None,
            'current_name': directions[-1]['next_name'],
            'dst':          destination_location,
            'length':       haversine(directions[-1]['dst'],
                                      directions[-1]['dst'], unit='m'),
            'mid':          directions[-1]['dst'],
            'next_name':    None,
            'src':          directions[-1]['mid']},

        {'angle':        None,
            'current_name': directions[-1]['next_name'],
            'dst':          None,
            'length':       haversine(destination_location,
                                      directions[-1]['dst'], unit='m'),
            'mid':          destination_location,
            'next_name':    None,
            'src':          directions[-1]['dst']},
    ])

    # Adds dictionary related to the source_location coordinates
    directions.insert(0,
                      {'angle':        None,
                       'current_name': None,
                       'dst':          directions[0]['mid'],
                       'length':       haversine(source_location,
                                                 directions[0]['src'],
                                                 unit='m'),
                       'mid':          directions[0]['src'],
                       'next_name':    directions[0]['current_name'],
                       'src':          source_location}
                      )

    return directions


def plot_directions(graph, source_location, destination_location, directions,
                    filename, width=400, height=400):
    """Plots the route from source_location to destination_location and saves
       in current directory an image of this plot, in .png format

    Args:
        graph: networkx-based graph
        source_location: (lat,lon) coordinates
        destination_location: (lat,lon) coordinates
        filename: image name string
        width, height: dimensions of the .png that contains the route plot
    """
    m = StaticMap(350, 350)

    # [::-1] reverses the coordinates; useful for staticmap lat-long
    # representation which need to be reverted
    for n in directions:
        m.add_line(Line((n['src'][::-1], n['mid'][::-1]), 'red', 4))
        m.add_marker(CircleMarker(n['src'][::-1], 'red', 10))
    m.add_marker(CircleMarker(destination_location[::-1],  'blue', 15))
    m.add_marker(CircleMarker(source_location[::-1], 'blue', 15))

    image = m.render()
    image.save(filename)
