# WatchSAC - SMS alerts for deals on SteepAndCheap

This is a webapp which scrapes the 'current steals' from steepandcheap.com and sends out SMS text alerts when the product's name and description are sufficiently similar to user-inputted search terms.

#### Things it does

 * SMS alerts based on fuzzily-matched search terms
 * Search term spelling corrector, built using words and phrases from previously seen product descriptions
 * a 'forecasting' page, which displays recent match count estimates for individual and aggregated searches

#### Stuff it uses
* Python (cherrypy) using HTTP Basic Auth and temporary tokens for security behind nginx for TLS support
* Vanilla JS front-end, with Skeleton CSS
* Twilio API for sending text messages
* RESTful API with MySQL back-end

#### Where it lives
* [right over here!](https://watchsac.com)


