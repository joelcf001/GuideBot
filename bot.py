# bot.py
"""bot.py
 Provides a telegram bot that will guide you from your current location to any
 place you want, through an interactive user chat experience. The bot uses
 several algorithms implemented with networkx on OpenStreetMaps maps, with the
 abstract layer of osmnx."""
# author: Joel Castaño Fernandez

import telegram.ext  # Bot only reacts importing before the lib
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from haversine import haversine
import guide
import osmnx as ox

TOKEN = open('token.txt').read().strip()
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher
G = guide.download_graph('Barcelona, Spain')


class UnknownLocationError(Exception):
    """Exception for unknown location situations"""
    pass


def author(update, context):
    """Displays the bot's author"""
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Author: Joel Castaño Fernández")


def start(update, context):
    """Initialization message of the bot"""
    info = '''
Welcome to the *GuideBot* %s 🧭
You are ready to find the shortest route to any place you want. \
Use the `/help` command for help.
    ''' % update.effective_chat.first_name
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=info,
        parse_mode=telegram.ParseMode.MARKDOWN)


def help(update, context):
    """Shows a brief description of the bot commands"""
    info = '''
Available commands:
·  `/start`: starts the conversation with the *GuideBot*.
·  `/help`: offers help on available commands.
·  `/author`: displays de author of the project.
·  `/go destination`: guides the user from his current location to the\
 _destination_. For instance: `/go` _Sagrada Família_
You *must* have live location enabled to use this command. GuideBot will\
 use your current location to guide you through the optimal route to your\
 destination using several checkpoints. You should follow them. Keep in mind\
 that telegram live location has a certain delay; if you go too fast between\
 checkpoints, one may be skipped. Finally, the bot will work in Barcelona;\
 even if the bot makes a route from your location to a place outside Barcelona\
, it is not guaranteed to be a good route.
·  `/where`: displays the current location of the user.
You *must* have live location enabled to use this command.
·  `/cancel`: stops the active guide system of the user.
You won't be able to make a new route until you cancel the current guide\
 system.
'''
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=info,
        parse_mode=telegram.ParseMode.MARKDOWN
    )


def go(update, context):
    """Starts the active user guide system, guiding the user from his location
       to his desired destination. More over, displays the shortest route image
       formatted in .png"""

    try:
        # checks if current location is available
        if 'location' not in context.user_data:
            raise UnknownLocationError

        source_location = context.user_data['location']

        # If a destination is already specified in user chat memory, this
        # destination is assigned; otherwise user's input is the destination.
        # This is useful when recalculating paths after skipping some node.
        destination_location = (
            ox.geocode(" ".join(context.args)) if 'destination' not in
            context.user_data else context.user_data['destination'])

        directions = guide.get_directions(G, source_location,
                                          destination_location)

    except guide.SameLocationError:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You are already in your destination!")

        cancel(update, context)
    except UnknownLocationError:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Your current location is unknown. Have you enabled live\
 location? If so, Telegram has not sent your location yet.")

    except Exception as e:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Bot could not compute the shortest route. Have you typed your\
 destination correctly? Is the destination in your city?")

        cancel(update, context)

    guide.plot_directions(G, source_location, destination_location,
                          directions, 'route.png')

    context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=open('route.png', 'rb')
    )

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='''
--------
You are at {:2f}, {:2f}
Start at checkpoint #1: {:3f}, {:3f} ({})
-------- *Remember*: type `/where` to know your location and `/cancel` to stop\
 the current guide system.
        ''' .format(*source_location, *directions[0]['src'],
                    directions[0]['next_name']),
        parse_mode=telegram.ParseMode.MARKDOWN
    )

    # Global variables that identify uniquely the current user guide system
    context.user_data['directions'] = directions
    context.user_data['checkpoint'] = 0
    context.user_data['destination'] = destination_location
    context.user_data['active'] = True


def orientation_phrase(angle, length, dst_name):
    """Returns the correct orientation between two checkpoints of the shortest
       path, formatted correctly and ready for its display in the user chat.

    Args: angle: angle between checkpoints
          length: length between checkpoints
          dst_name: destination checkpoint street
    """
    # angle == None when user's next checkpoint is the end.
    if angle is None:
        return "Keep going until your last checkpoint!"
    if angle < 0:
        angle += 360

    # We normalize the angle, and find the right turn
    a = (angle+22.5)//45
    length = 5*round(length/5)  # Approximates length to a multiple of 5

    if a == 0 or a == 8:
        return "Go straight through {} {} m".format(dst_name, length)
    if a == 1:
        return "Turn slightly to the right in {} m".format(length)
    if a == 2:
        return "Turn to the right in {} m".format(length)
    if a == 3:
        return "Turn strongly to the right in {} m".format(length)
    if a == 4:
        return "Turn back straight through {} {} m".format(length,
                                                           dst_name)
    if a == 5:
        return "Turn strongly to the left in {} m".format(length)
    if a == 6:
        return "Turn to the left in {} m".format(length)
    if a == 7:
        return "Turn slightly to the left in {} m".format(length)


def cancel(update, context):
    """Stops the active user guide system and cleans the user chat memory"""

    # If 'active' attr is in user_data, /go command has been executed so the
    # guide system is active
    if 'active' in context.user_data:
        context.user_data['active'] = False
        del (context.user_data['checkpoint'],
             context.user_data['directions'],
             context.user_data['destination'],
             context.user_data['active'])

        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='''
Your current guide has been stopped!
Please, type `/go destination` if you want a new route.
--------
            ''',
            parse_mode=telegram.ParseMode.MARKDOWN)

    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='''
There is no route active!
Please, type `/go destination` if you want a new route.
            ''',
            parse_mode=telegram.ParseMode.MARKDOWN
        )


def print_next_checkpoint(update, context):
    """Displays in chat the arrival of the user to the next checkpoint.
       More over, indicates the next checkpoint, the needed orientation, and
       the length from his current location to the next checkpoint."""

    # Initializes needed variables for correct displaying for better reading
    src_location = context.user_data['location']
    checkpoint = context.user_data['checkpoint']
    directions = context.user_data['directions']
    dst_location = directions[checkpoint]['dst']
    dst_name = directions[checkpoint]['next_name']
    angle = directions[checkpoint+1]['angle']
    length = directions[checkpoint+1]['length']

    # Checkpoint visited, we increase the total counter
    context.user_data['checkpoint'] += 1

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='''

Well done: You have reached checkpoint {}!
You are at {:2f}, {:2f}
Go to checkpoint {}: {:3f}, {:3f} ({}). {}.
        ''' .format(checkpoint+1,  *src_location, checkpoint+2, *dst_location,
                    dst_name, orientation_phrase(angle, length, dst_name)),
        parse_mode=telegram.ParseMode.MARKDOWN
    )


def print_end_checkpoint(update, context):
    """Displays in chat the user's arrival to the last checkpoint of its route.
       More over, cancels the active user guide system"""

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='''
Congratulations! *You have reached your destination*
Current guide will be stopped...
--------''',
        parse_mode=telegram.ParseMode.MARKDOWN
    )

    cancel(update, context)


def recalculate_route(update, context):
    """Recalculates the route of the active user guide system in case the user
       skipped a checkpoint. This recalculation implies a whole new global
       directions list and a new shortest path calculation with its .png image
       displayed in chat."""

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='''The checkpoint {} has been skipped or you have taken a wrong\
 route... The route is being recalculated and the chekpoints reseted.'''
        .format(context.user_data['checkpoint']+1),
        parse_mode=telegram.ParseMode.MARKDOWN
    )

    # reuses go command to recalculate the route
    go(update, context)


def new_location(update, context):
    """Updates the current location of the user everytime a new location is
       received. In case the user guide system is active, it checks if user
       location is near the checkpoint. If user has skipped a checkpoint
       the whole rute is recalculated"""

    msg = update.edited_message if update.edited_message else update.message
    src_location = (msg.location.latitude, msg.location.longitude)
    context.user_data['location'] = src_location
    if 'previous_location' not in context.user_data:
        context.user_data['previous_location'] = src_location

    # This new-location is checked if the user guide system is active
    if context.user_data['active']:
        directions = context.user_data['directions']
        checkpoint = context.user_data['checkpoint']
        next_location = directions[checkpoint]['mid']
        previous_location = context.user_data['previous_location']

        # Computes distances to the next checkpoint of current and previous
        # location
        prev_ε = haversine(previous_location, next_location, unit='m')
        ε = haversine(src_location, next_location, unit='m')

        context.user_data['previous_location'] = src_location
        # If previous location was closer to the next checkpoint, assuming
        # every street turn has a checkpoint, this implies that user has
        # skipped a checkpoint, probably due to telegram's delay, or he
        # has taken a wrong path. We recalculate te route. Also, we take a
        # +10 meters interval to avoid errors.
        if prev_ε + 10 < ε:
            recalculate_route(update, context)
        else:
            # If current distance to the checkpoint is less than 17m, user
            # arrived to the checkpoint
            if ε < 17:
                if directions[checkpoint]['next_name'] is None:
                    print_end_checkpoint(update, context)
                else:
                    print_next_checkpoint(update, context)


def unknown(update, context):
    """Displayed when user introduces a wrong command"""
    context.bot.send_message(
        chat_id=update.message.chat_id,
        text='''Sorry, I didn't understand that command.\
 Type `/help` to know the available commands.''',
        parse_mode=telegram.ParseMode.MARKDOWN)


def where(update, context):
    """Displays the current user location"""
    try:
        if 'location' not in context.user_data:
            raise UnknownLocationError
        lat = context.user_data['location'][0]
        lon = context.user_data['location'][1]

    except:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Your current location is unknown. Have you enabled live\
 location? If so, Telegram has not sent your location yet.")

    context.bot.send_location(
        chat_id=update.effective_chat.id,
        latitude=lat,
        longitude=lon)

    update.message.reply_text(str((lat, lon)))


dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('author', author))
dispatcher.add_handler(CommandHandler('help', help))
dispatcher.add_handler(CommandHandler('go', go))
dispatcher.add_handler(CommandHandler('where', where))
dispatcher.add_handler(CommandHandler('cancel', cancel))
dispatcher.add_handler(MessageHandler(Filters.location, new_location))
dispatcher.add_handler(MessageHandler(Filters.command, unknown))


updater.start_polling()
