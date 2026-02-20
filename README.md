# is-the-mountain-out
Determine via streaming training if the mountain is out

## strategy
- Get a list of webcams and train a model using Online Learning
- Apply easy optimizations by incorporating time of day (no mountain at night) and METAR weather data (if visibility is less than X, highly unlikely the mountain is out
- Raise github PRs with a link to a github page showing images captured at the same time and weather data for users or agents to classify with labels
- Authorized users can raise GitHub issues identifying when they see the mountain and from what location to fine tune the model
- Model iteratively updates and produces a new GitHub page with simple message announcing if the mountain is out or not
- Add a map with a probability chloropleth overlay indicating likelihood that the mountain is out, along with links to webcams used to train and thumbnails of their current status
