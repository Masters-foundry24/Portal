# This is the program that we run when we launch our website. It needs to be 
# out side the website folder because we are treating the website as a packaged,
# somewhat equal to pandas.

from website import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host = "0.0.0.0", port = 5000, debug = True)
    # To access this page on my phone I can enter "ipconfig" into a bash
    # terminal and get my local IP address which is listed as "IPv4 Address".
    # Then I can get on my phone and enter "http://[my_IP_address]:5000". Make
    # sure that your VPN, in both the computer and phone is turned off for this.
    # app.run(debug = True) # Use debug when building, not in production