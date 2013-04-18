from flamejam import app, db
from flamejam.utils import get_slug
from flamejam.models import Jam, Game, User, Comment, GamePackage, \
    GameScreenshot, JamStatusCode, Rating
from flamejam.forms import WriteComment, GameEditForm, GameAddScreenshotForm, \
    GameAddPackageForm, GameAddTeamMemberForm, GameCreateForm, RateGameForm
from flask import render_template, url_for, redirect, flash, request
from flask.ext.login import login_required, current_user

@app.route("/jams/<jam_slug>/create-game/", methods = ("GET", "POST"))
@login_required
def create_game(jam_slug):
    jam = Jam.query.filter_by(slug = jam_slug).first_or_404()

    r = current_user.getRegistration(jam)
    if not r or not r.team:
        flash("You cannot create a game without being registered for the jam.", category = "error")
        return redirect(jam.url())
    if r.team.game:
        flash("You already have a game.")
        return redirect(r.team.game.url())

    enabled = (JamStatusCode.RUNNING <= jam.getStatus().code <= JamStatusCode.PACKAGING)

    form = GameCreateForm(request.form, obj = None)
    if enabled and form.validate_on_submit():
        game = Game(r.team, form.title.data)
        db.session.add(game)
        db.session.commit()
        return redirect(url_for("edit_game", jam_slug = jam_slug, game_slug = game.slug))

    return render_template("jam/game/create.html", jam = jam, enabled = enabled, form = form)

@app.route("/jams/<jam_slug>/<game_slug>/edit/", methods = ("GET", "POST"))
@login_required
def edit_game(jam_slug, game_slug):
    jam = Jam.query.filter_by(slug = jam_slug).first_or_404()
    game = jam.games.filter_by(slug = game_slug).first_or_404()

    if not game or not current_user in game.team.members:
        abort(403)

    form = GameEditForm(request.form, obj = game)
    package_form = GameAddPackageForm()
    screenshot_form = GameAddScreenshotForm()

    if form.validate_on_submit():
        print "OMG"
        slug = get_slug(form.title.data)
        print slug
        if not jam.games.filter_by(slug = slug).first() in (game, None):
            flash("A game with a similar title already exists. Please choose another title.", category = "error")
        else:
            form.populate_obj(game)
            print form.help.data
            game.slug = get_slug(game.title)
            db.session.commit()
            flash("Your settings have been applied.", category = "success")
            return redirect(game.url())

    if package_form.validate_on_submit():
        s = GamePackage(game, package_form.url.data, package_form.type.data)
        db.session.add(s)
        db.session.commit()
        flash("Your package has been added.", "success")
        return redirect(request.url)

    if screenshot_form.validate_on_submit():
        s = GameScreenshot(screenshot_form.url.data, screenshot_form.caption.data, game)
        db.session.add(s)
        db.session.commit()
        flash("Your screenshot has been added.", "success")
        return redirect(request.url)

    return render_template("jam/game/edit.html", jam = jam, game = game,
        form = form, package_form = package_form, screenshot_form = screenshot_form)

@app.route('/edit/package/<id>/<action>/')
@login_required
def game_package_edit(id, action):
    if not action in ("delete"):
        abort(404)

    p = GamePackage.query.filter_by(id = id).first_or_404()
    if not current_user in p.game.team.members:
        abort(403)

    if action == "delete":
        db.session.delete(p)
    db.session.commit()
    return redirect(url_for("edit_game", jam_slug = p.game.jam.slug, game_slug = p.game.slug))

@app.route('/edit/screenshot/<id>/<action>/')
@login_required
def game_screenshot_edit(id, action):
    if not action in ("up", "down", "delete"):
        abort(404)

    s = GameScreenshot.query.filter_by(id = id).first_or_404()
    if not current_user in s.game.team.members:
        abort(403)

    if action == "up":
        s.move(-1)
    elif action == "down":
        s.move(1)
    elif action == "delete":
        db.session.delete(s)
        i = 0
        for x in s.game.screenshotsOrdered:
            x.index = i
            i += 1
    db.session.commit()
    return redirect(url_for("edit_game", jam_slug = s.game.jam.slug, game_slug = s.game.slug))

@app.route('/jams/<jam_slug>/<game_slug>/', methods = ("POST", "GET"))
def show_game(jam_slug, game_slug):
    comment_form = WriteComment()
    jam = Jam.query.filter_by(slug = jam_slug).first_or_404()
    game = Game.query.filter_by(slug = game_slug).filter_by(jam = jam).first_or_404()

    if current_user.is_authenticated() and comment_form.validate_on_submit():
        comment = Comment(comment_form.text.data, game, current_user)
        db.session.add(comment)
        db.session.commit()
        flash("Your comment has been posted.", "success")
        return redirect(game.url())

    return render_template('jam/game/info.html', game = game, form = comment_form)

@app.route("/jams/<jam_slug>/<game_slug>/rate/", methods = ("GET", "POST"))
@login_required
def rate_game(jam_slug, game_slug):
    jam = Jam.query.filter_by(slug = jam_slug).first_or_404()
    game = jam.games.filter_by(slug = game_slug).first_or_404()

    form = RateGameForm()
    if jam.getStatus().code != JamStatusCode.RATING:
        flash("This jam is not in the rating phase. Sorry, but you cannot rate right now.", "error")
        return redirect(game.url())

    if current_user in game.team.members:
        flash("You cannot rate on your own game. Go rate on one of these!", "warning")
        return redirect(url_for("jam_games", jam_slug = jam.slug))

    rating = game.ratings.filter_by(user = current_user).first()
    if rating:
        flash("You are editing your previous rating of this game.", "info")

    if form.validate_on_submit():
        new = rating == None
        if not rating:
            rating = Rating(game, current_user, form.note.data, form.score.data)
            db.session.add(rating)
        else:
            rating.text = form.note.data

        for c in ["overall"] + game.ratingCategories:
            rating.set(c, form.get(c).data)

        db.session.commit()
        flash("Your rating has been " + ("submitted" if new else "updated") + ".", "success")
        return redirect(url_for("jam_games", jam_slug = jam.slug))

    elif rating:
        for c in ["overall"] + game.ratingCategories:
            form.get(c).data = rating.get(c)
        form.note.data = rating.text

    return render_template('jam/game/rate.html', jam = jam, game = game, form = form)