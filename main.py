# This is the program that we run when we launch our website. It needs to be 
# out side the website folder because we are treating the website as a packaged,
# somewhat equal to pandas.

from website import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug = True) # Use debug when building, not in production