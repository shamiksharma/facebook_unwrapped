#-----------------------------------------------------------------------
# This program was a learning exercise to understand the sequence of calls
# used in Facebook Oauth. For that reason, it uses only standard Python
# to make the necessary HTTP calls. 
#
# It turns out that most FB "wrapper" libraries, drag along a lot of crud,
# and wrapper the core FB calls deep inside themselves. When FB apis change
# (as they do a lot), it is a nightmare to chase down the issue. 
#
# If you like everything under your own control, just copy this code 
# and modify as you wish. All it does is make HTTP calls using urllib.
#
# The only "magic" state it needs is the access-token in a cookie called "user"
#
# 0. Installation and pre-requirements
#    This program only needs standard python - you dont need any other library.
#    Just copy this file to any directory and its ready to run.
#
# 1. Create a FB application at http://www.facebook.com/developers/createapp.php
#      App name :  foo123bar456
#      Website Tab > Site URL :  http://localhost:8080/     <--- your laptop/desktop
#      FacebookTab > Canvas Page : http://apps.facebook.com/foo123bar456/
#
# 2. Go to your app-settings page  
#    http://www.facebook.com/developers/apps.php
#    and get the app_id,  api_key and app_secret 
#    Update the fields marked "xxxx" in this program.
#     
# 3. Run this app
#    % python facebook_unwrapped.py
#
# 4. Go to a browser and go to the app :  http://apps.facebook.com/foo123bar456/
#    You should go through the Oauth process and see your name, email, and ids of your friends.
#    Go to the URL on a second tab/window - this time you should not need auth.
# 
# 5. If you want to run the auth sequence multiple times, you need to clear state.
#    a) You need to tell FB to deauthorize the app, here:
#        http://www.facebook.com/settings/?tab=applications
#    b) Clear the cookie issued by "localhost". 
#        For Chrome, you can do that here: chrome://settings/cookies
#------------------------------------------------------------------------

import os
import sys
import BaseHTTPServer
import Cookie
import json
import urllib
import urllib2
from urlparse import urlparse

#-----------------------------------------------------------------------
# Based on  
#     http://developers.facebook.com/docs/authentication/
#
# Facebook Graph auth sequence is :
#  - FB calls your SiteURL with POST.
#  - You will find that "user" cookie is not there, so will send to LoginHandler
#  - LoginHandler redirect to fb_auth_url with perms requested and CallbackPage
#  - FB sends a "code" back to CallbackPage in URI.
#  - CallbackPage calls fb_get_token_url with appid/appsecret/code and NextPage
#  - FB sends a "access_token" to NextPage in URI
#  - NextPage can make Fb-api calls with access_token
#-----------------------------------------------------------------------

fb_app_page    = "http://apps.facebook.com/xxx-myapp-xxxx/"
fb_app_id      = "xxxxxxx"
fb_app_key     = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
fb_app_secret  = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
server_redirect_mode = True
the_cookie_name      = "user"
the_port       = 8080

#
# Overwrite/define the params defined above using a local myconfig.py file 
# This lets you keep the secret in a safer file.
#
try:
  from myconfig import *
except ImportError: pass

#
# Some FB endpoints
#

fb_auth_url    = "https://www.facebook.com/dialog/oauth" 
fb_token_url   = "https://graph.facebook.com/oauth/access_token"
fb_graph_url   = "https://graph.facebook.com/me"

#---------------------------------------------------------------------


class MainHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  _access_token = None 

  #
  # Writes out the HTTP response and if there is a accesstoken
  # it inserts that into the user-cookie
  #
  def writeResponse(self, content):
    self.send_response(200)
    self.send_header("Content-type", "text/html")
    if (self._access_token): 
       self.send_header("Set-Cookie", the_cookie_name + "=" + self._access_token)
    self.end_headers()
    self.wfile.write("<html><body>" + content + "</body></html>")
    return
 
  #
  # read the cookie string from the HTTP request and get the cookie value
  #
  def get_token_from_cookie(self, cookie_name=the_cookie_name):
    cookies_string = self.headers.get('Cookie')
    if cookies_string:
      # parse the string into a dictionary of cookie objects
      cookies = Cookie.SimpleCookie(cookies_string)
      # extract the value of the cookie called 'user'
      user_string = cookies[cookie_name].value
      return user_string
    else:  
      return None

  #
  # get a url param. 
  # Given a url like http://host?...&code=xxxxx&...  get_urlarg("code") => xxxx
  #
  def get_urlarg(self, name):
    try:
      url = urlparse(self.path)
      urlargs = [part.split('=') for part in url[4].split('&')]
      params = dict(urlargs)
      if params.has_key(name):
        return params[name]
      else:
        return None
    except:
      return None

  #
  # Just write the response header
  #
  def redirect(self, redirect_uri):
    self.send_response(302)  
    self.send_header("Content-type",  "text/html")
    self.send_header("Location ",     redirect_uri)
    self.send_header("Connection",    "close")
    self.send_header("Cache-control", "private")
    self.end_headers() 
    self.wfile.write("redirecting..")  
   
  #
  # Client might be in three states, when this call comes in.
  #
  # 1. Brand new user - no token-in-cookie, and no code in url-arg
  # 2. In process of authenticating - no token, but code present in url-arg
  # 3. Authenticated user - has token in cookie
  # 
  def do_POST(self):

    #
    # Look for token and code to determine which state the client is in.
    #
    user_token = self.get_token_from_cookie(the_cookie_name)
    code = self.get_urlarg("code")

    # Common params used in fb calls.
    params = {'client_id':fb_app_id, 'redirect_uri':fb_app_page}

    #
    # State-3: I have the token, can make fbapi call.
    #
    #
    if user_token: 
      self._access_token = user_token       

    #
    # State-2: I have the code, get the acces_token
    # 
    # Send the code back to FB showing that the user agreed to the perms.
    # FB associates those perms with your app, by checking your secret.
    # It then issues you a token that can be used to make FB-api calls.
    #
    # Note that this is not a redirect. At the end of this codeblock
    # you have an access-token, so you are in State-3, so you can go ahead
    # and make FB-api calls.
    #
    elif code    : 
      params['code'] = code
      params['client_secret']= fb_app_secret
      request = urllib2.Request(fb_token_url, data= urllib.urlencode(params) )
      access_token = urllib2.urlopen(request).read()
      self._access_token = access_token

    #
    #  State-1: Need to get the code first and then come back.
    #
    #  This is done by redirecting the user to FB oauth/authorize?scope="perms-you-want"
    #  FB will pop up the perms dialog to get the user's permissions and send you back
    #  to your redirect_uri. This does not need any secret information.
    #
    #  You may see a "Go to Facebook" page before the perms dialog,
    #  due to this FB bug: http://goo.gl/ychaf
    #  As documented at that link, the way to avoid that is to use client-side redirects.
    #  To use that, set the server_redirect_mode to False at the top.
    #
    #  Note that the return at the end of this block is important.  
    #  The HTTPRespnse (redirect) will not be sent until this method returns.
    #
    #
    else:
      params['scope'] = "user_about_me"

      if server_redirect_mode:
        auth_url = fb_auth_url + "?" + urllib.urlencode(params)
        self.redirect(auth_url)
        return
      else:
        params['response_token'] = "token"
        auth_url = fb_auth_url + "?" + urllib.urlencode(params)
        self.writeResponse('<script> top.location.href="'+auth_url+'";</script>')
        return

    #
    # by now, self._access_token should hold the token
    # Make an fb api call and put the user json data into a dictionary.
    #
    fields = "name,email,picture,friends"
    graph_url = "%s?%s&fields=%s" % (fb_graph_url, self._access_token, fields)
    print graph_url
    request   = urllib2.Request(graph_url, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    response  = urllib2.urlopen(request).read()

    #
    # Take the json response and convert it into a dictionary
    # Grab some fields from it.
    #
    user_me   = json.loads(response)

    friends = [user_me['id'] for user in user_me['friends']['data']]
    name    = user_me['name'],
    email   = user_me.get('email'),
    picture = user_me['picture']

    #
    # Write some response using fb data. Put the user=access_token cookie in there.
    #
    self.writeResponse('<html><body> name: %s <br> email %s <br> pic: %s <br> friends: %s </body></html>' % (name, email, picture, friends))
    
    return

#-----------------------------------------------------------------------
# Start the built-in python httpserver
#

def main():
  server = BaseHTTPServer.HTTPServer(('', the_port), MainHandler)
  print "Server listening at port http://localhost:" + str(the_port) + "/"
  server.serve_forever()

if __name__ == "__main__":
  main()
#-----------------------------------------------------------------------


