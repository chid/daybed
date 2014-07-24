from cornice import Service
from daybed import __version__ as VERSION


hello = Service(name="hello",
                path='/',
                description="Welcome",
                renderer="jsonp")


@hello.get()
def get_hello(request):
    """Return information regarding the current instance."""
    return dict(token=request.token,
                daybed='hello',
                version=VERSION,
                url=request.host_url)
