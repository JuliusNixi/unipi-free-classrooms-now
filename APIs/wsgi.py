from apis import *

# Used in production.
if __name__ == "__main__":

    main()

    app.run()
else:
    # Gunicon takes this as the entry point and automatically runs the app.
    main()
