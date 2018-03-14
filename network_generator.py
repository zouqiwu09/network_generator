import twitter
import json
import sys
import time
from urllib2 import URLError
from httplib import BadStatusLine
"""
Login function (from cookbook)

"""
def oauth_login():
    CONSUMER_KEY = '09RpgWjQRId9OTusljygc2Wmv'
    CONSUMER_SECRET = 'cWx4l6oD6M3n4pX1ARurQfPbRzV9jYunhF4pu6fpu5EcHJtizy'
    OAUTH_TOKEN='958418693083549696-BYLrMCW32guPZ5SqqXenQem5cP5jGQK'
    OAUTH_TOKEN_SECRET='5jSmekrWQ2JmzqXhhVRPmjEkM1q2N2YqR12ySU3qPcIGQ'
    auth = twitter.OAuth(OAUTH_TOKEN,OAUTH_TOKEN_SECRET,CONSUMER_KEY,CONSUMER_SECRET)
    twitter_api = twitter.Twitter(auth = auth)
    return twitter_api

"""
Used to make twitter request (from cookbook)

"""
def make_twitter_request(twitter_api_func, max_errors=10, *args, **kw):
    # A nested helper function that handles common HTTPErrors. Return an updated
    # value for wait_period if the problem is a 500 level error. Block until the
    # rate limit is reset if it's a rate limiting issue (429 error). Returns None
    # for 401 and 404 errors, which requires special handling by the caller.
    def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):

        if wait_period > 3600:  # Seconds
            print >> sys.stderr, 'Too many retries. Quitting.'
            raise e

        # See https://dev.twitter.com/docs/error-codes-responses for common codes

        if e.e.code == 401:
            print >> sys.stderr, 'Encountered 401 Error (Not Authorized)'
            return None
        elif e.e.code == 404:
            print >> sys.stderr, 'Encountered 404 Error (Not Found)'
            return None
        elif e.e.code == 429:
            print >> sys.stderr, 'Encountered 429 Error (Rate Limit Exceeded)'
            if sleep_when_rate_limited:
                print >> sys.stderr, "Retrying in 15 minutes...ZzZ..."
                sys.stderr.flush()
                time.sleep(60 * 15 + 5)
                print >> sys.stderr, '...ZzZ...Awake now and trying again.'
                return 2
            else:
                raise e  # Caller must handle the rate limiting issue
        elif e.e.code in (500, 502, 503, 504):
            print >> sys.stderr, 'Encountered %i Error. Retrying in %i seconds' % (e.e.code, wait_period)
            time.sleep(wait_period)
            wait_period *= 1.5
            return wait_period
        else:
            raise e

    # End of nested helper function

    wait_period = 2
    error_count = 0

    while True:
        try:
            return twitter_api_func(*args, **kw)
        except twitter.api.TwitterHTTPError, e:
            error_count = 0
            wait_period = handle_twitter_http_error(e, wait_period)
            if wait_period is None:
                return
        except URLError, e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print >> sys.stderr, "URLError encountered. Continuing."
            if error_count > max_errors:
                print >> sys.stderr, "Too many consecutive errors...bailing out."
                raise
        except BadStatusLine, e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print >> sys.stderr, "BadStatusLine encountered. Continuing."
            if error_count > max_errors:
                print >> sys.stderr, "Too many consecutive errors...bailing out."
                raise

"""
Used to get user profile json (from cookbook)

"""
def get_user_profile(twitter_api, screen_names=None, user_ids=None):
    # Must have either screen_name or user_id (logical xor)
    assert (screen_names != None) != (user_ids != None), "Must have screen_names or user_ids, but not both"

    items_to_info = {}

    items = screen_names or user_ids

    while len(items) > 0:

        # Process 100 items at a time per the API specifications for /users/lookup.
        # See https://dev.twitter.com/docs/api/1.1/get/users/lookup for details.

        items_str = ','.join([str(item) for item in items[:100]])
        items = items[100:]

        if screen_names:
            response = make_twitter_request(twitter_api.users.lookup,
                                            screen_name=items_str)
        else:  # user_ids
            response = make_twitter_request(twitter_api.users.lookup,
                                            user_id=items_str)
        #if (response == None):
        #    continue

        for user_info in response:
            if screen_names:
                items_to_info[user_info['screen_name']] = user_info
            else:  # user_ids
                items_to_info[user_info['id']] = user_info

    return items_to_info

"""

My crawler

@twitter_api:  the api object
@user_id_list: the list of user id that we need to crawl
@account_container: the container used to store the collected user ids
@Graph: the graph object that used to add nodes and edge on graph

"""
def crawl_friends_followers(twitter_api, user_id_list, account_container, Graph):
    #print(user_id_list)
    """ If we have already collected enough accounts or there is no enough ids to crawl, end the function """
    if (len(account_container) >= 100 or len(user_id_list) == 0):
        return
    for user_id in user_id_list:
        """ If we have already collected enough accounts, end the function"""

        if (len(account_container) >= 100):
            break

        """ Get friends list and followers list"""

        friends_list, followers_list = get_friends_followers_ids(twitter_api=twitter_api, user_id=user_id,
                                                                 friends_limit=5000, followers_limit=5000)
        """ Get reciprocal friends"""

        reciprocal_friends = set(followers_list) & set(friends_list)

        """ If this user don't have any reciprocal friend, skip and continue"""

        if (reciprocal_friends == None):
            continue
        """ Get user profile so that we can get the followers count"""

        users_info = get_user_profile(twitter_api=twitter_api, user_ids=list(reciprocal_friends))

        """ Get a dictionary whose key is user id and value is followers count, and do not count the user id that has already been collected before"""

        followers_num_dict = {x: users_info[x]["followers_count"] for x in reciprocal_friends if not (x in account_container)}

        """ 
            Sort the dictionary based on key and get the list of user ids
            Then get the top 5 popular user ids
        """

        most_popular_friends = sorted(followers_num_dict, reverse=True, key=followers_num_dict.get)[0:5]


        """ Get the user id who is the reciprocal friends with current user id and has been collected in social network before"""

        overlap = set(reciprocal_friends) & set(account_container)
        for friend in list(overlap):

            """ Add edge between them"""

            Graph.add_edge(user_id, friend)
        for x in most_popular_friends:

            """ Add edge between current user_id and the top 5 popular reciprocal friends"""

            Graph.add_edge(user_id, x)

            """ Add the list of friends to account container"""

        account_container += most_popular_friends

        """ Remove this id from the list of user ids that we need to crawl"""

        user_id_list.remove(user_id)

        """ Add the top 5 popular friends to the list of ids that we need to crawl """

        user_id_list += most_popular_friends

    crawl_friends_followers(twitter_api, user_id_list, account_container, Graph)

""" 
Used to get friends and followers (from cookbook)

"""

from functools import partial
from sys import maxint
def get_friends_followers_ids(twitter_api, screen_name=None, user_id=None,
                              friends_limit=maxint, followers_limit=maxint):
    # Must have either screen_name or user_id (logical xor)
    assert (screen_name != None) != (user_id != None), "Must have screen_name or user_id, but not both"

    # See https://dev.twitter.com/docs/api/1.1/get/friends/ids and
    # https://dev.twitter.com/docs/api/1.1/get/followers/ids for details
    # on API parameters

    get_friends_ids = partial(make_twitter_request, twitter_api.friends.ids,
                              count=5000)
    get_followers_ids = partial(make_twitter_request, twitter_api.followers.ids,
                                count=5000)

    friends_ids, followers_ids = [], []

    for twitter_api_func, limit, ids, label in [
        [get_friends_ids, friends_limit, friends_ids, "friends"],
        [get_followers_ids, followers_limit, followers_ids, "followers"]
    ]:

        if limit == 0: continue

        cursor = -1
        while cursor != 0:

            # Use make_twitter_request via the partially bound callable...
            if screen_name:
                response = twitter_api_func(screen_name=screen_name, cursor=cursor)
            else:  # user_id
                response = twitter_api_func(user_id=user_id, cursor=cursor)

            if response is not None:
                ids += response['ids']
                cursor = response['next_cursor']

            print >> sys.stderr, 'Fetched {0} total {1} ids for {2}'.format(len(ids),
                                                                            label, (user_id or screen_name))

            # XXX: You may want to store data during each iteration to provide an
            # an additional layer of protection from exceptional circumstances

            if len(ids) >= limit or response is None:
                break

    # Do something useful with the IDs, like store them to disk...
    return friends_ids[:friends_limit], followers_ids[:followers_limit]

import networkx as nx
import matplotlib.pyplot as plt
G = nx.Graph()
twitter_api = oauth_login()
screen_name = "KattyPerry4U"

""" Get reciprocal friends """
friends_list, followers_list = get_friends_followers_ids(twitter_api= twitter_api, screen_name = screen_name, friends_limit= 5000, followers_limit= 5000)

reciprocal_friends = set(followers_list) & set(friends_list)

users_info = get_user_profile(twitter_api = twitter_api, user_ids = list(reciprocal_friends))

""" Get 5 most popular friends """
followers_dict = {x:users_info[x]["followers_count"] for x in reciprocal_friends}
most_popular_friends = sorted(followers_dict, reverse= True, key= followers_dict.get)[0:5]

account_list = []
id = twitter_api.users.show(screen_name=screen_name)['id']

""" Add the initial node in account list that we need to crawl """

account_list.append(id)
account_list+= most_popular_friends
id_container = list(account_list)

""" Add edge between first node and the 5 popular friends """

for x in id_container:
    G.add_edge(id, x)

""" Start crawling """
crawl_friends_followers(twitter_api = twitter_api, user_id_list= account_list, account_container= id_container, Graph = G)

print ("colleted nodes: ", id_container)
nx.draw(G)

""" Save the picture and show"""

plt.savefig("graph.png")
plt.show()
print ("nodes: ", nx.nodes(G))
print ("edges: ", nx.edges(G))
print ("number of nodes: ", len(nx.nodes(G)))
print ("number of edges: ", len(nx.edges(G)))
print ("diameter: ", nx.diameter(G))
print ("average shortest path length: ", nx.average_shortest_path_length(G))

""" Write to file """

with open('./networkInfo.txt', 'w+') as f:
    f.write("Nodes: ")
    f.write(str(nx.nodes(G)))
    f.write("\nEdges: ")
    f.write(str(nx.edges(G)))
    f.write("\nNumber of nodes: ")
    f.write(str(len(nx.nodes(G))))
    f.write("\nNumber of edges: ")
    f.write(str(len(nx.edges(G))))
    f.write("\nDiameter: ")
    f.write(str(nx.diameter(G)))
    f.write("\nAverage shortest path length: ")
    f.write(str(nx.average_shortest_path_length(G)))
    f.close()
