import json
from flask import render_template, request, redirect, flash, url_for, session, jsonify, make_response, current_app
from models import explanation, observation, location, explanation_observation, explanation_type, observation_type, explanation_location, User, db
from application import app, bcrypt, login_manager
from flask_login import login_user , logout_user , current_user , login_required
from datetime import timedelta
from functools import update_wrapper
login_manager.login_view = 'login'


@login_manager.user_loader
def user_loader(user_id):
    return User.query.get(int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('login'))

def crossdomain(origin=None, methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, list):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, list):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    if len(request.form) > 1 and len(request.form)<6:
        user = User.query.filter_by(username=request.form['username']).first()
        if user:
            if bcrypt.check_password_hash(user.password, request.form['password']):
                user.authenticated = True
                db.session.add(user)
                db.session.commit()
                login_user(user, remember=False)
                flash('Logged in successfully')
                return redirect(request.args.get('next') or url_for('index'))
            else:
                flash('Password is invalid', 'error')
                return redirect(url_for('login'))
        else:
            flash('Username or Password is invalid', 'error')
            return redirect(url_for('login'))
    if len(request.form) == 6:
        username = request.form['username']
        if request.form['password'] == request.form['rpassword']:
            password = bcrypt.generate_password_hash(request.form['password'])
        else:
            flash('Password is invalid', 'error')
            return redirect(url_for('login'))
        user = User(username=username, password=password, email=request.form['email'], name=request.form['fullname'])
        db.session.add(user)
        db.session.commit()
        flash('User successfully registered')
    return redirect(url_for('login'))


@app.route('/logout', methods=["GET"])
@login_required
def logout():
    user = current_user
    user.authenticated = False
    db.session.add(user)
    db.session.commit()
    logout_user()
    session['signed'] = False
    return redirect('/')


@app.route('/all', methods=["GET"])
@login_required
def all():
    return render_template(
        'all.html',
        all=explanation.query.all()
    )

@app.route('/allob', methods=["GET"])
@login_required
def allob():
    return render_template(
        'allob.html',
        all=observation.query.all()
    )

@app.route('/', methods=["GET"])
@login_required
def index():
    te = explanation.query.count()
    drug = explanation.query.filter_by(typeid=3).count()
    return render_template(
        'index.html',
        a=te-drug,
        b=drug,
        c=observation.query.count(),
        d=User.query.count()
    )


@app.route('/s', methods=['GET', 'POST'])
@login_required
def search_explanation():
    e = explanation.query.filter(explanation.name.ilike('%' + str(request.form['exs']) + '%')).all()
    if e is None:
        return redirect('/')
    else:
        return render_template(
            'all.html',
            all=e
        )


@app.route('/so', methods=['GET', 'POST'])
@login_required
def search_observation():
    e = observation.query.filter(observation.name.ilike('%' + str(request.form['obs']) + '%')).all()
    if e is None:
        return redirect('/')
    else:
        return render_template(
            'allob.html',
            all=e
        )


@app.route('/u<int:explanation_id>', methods=['GET', 'POST'])
@login_required
def update_explanation(explanation_id):
    e = explanation.query.get(explanation_id)
    et = explanation_type.query.all()
    el = location.query.all()
    if request.method == 'GET':
        return render_template(
            'update.html',
            e=e,
            et=et,
            el=el
        )
    else:
        name = request.form['explanation']
        tid = request.form['type']
        lid = request.form.getlist('location')
        e.typeid = tid
        e.name = name
        db.session.commit()
        for l in e.locations:
            el = explanation_location.query.filter_by(explanation_id=e.id, location_id=l.location.id).first()
            if el is None:
                break
            else:
                db.session.delete(el)
        db.session.commit()
        for l in lid:
            el = explanation_location(explanation_id=e.id, location_id=l)
            db.session.add(el)
            db.session.commit()
        exobservations = request.form.getlist('obs')
        exweight = request.form.getlist('weight')
        for o in e.observations:
            eo = explanation_observation.query.filter_by(explanation_id=e.id, observation_id=o.observation.id).first()
            if eo is None:
                break
            else:
                db.session.delete(eo)
        for i in range(len(exobservations)):
            if exobservations[i] == "" or exweight[i] == "":
                continue
            s = observation.query.filter_by(name=exobservations[i]).first()
            if s is None:
                s = observation(name=request.form['observation'])
                db.session.add(s)
                db.session.commit()
            s = observation.query.filter_by(name=exobservations[i]).first()
            ds = explanation_observation(explanation_id=e.id, observation_id=s.id, weight=exweight[i])
            db.session.add(ds)
        db.session.commit()
        print(len(request.form))
        return redirect('/all')

@app.route('/d<int:explanation_id>', methods=['GET'])
@login_required
def delete_explanation(explanation_id):
    if request.method == 'GET':
        e = explanation.query.get(explanation_id)
        for o in e.observations:
            eo = explanation_observation.query.filter_by(explanation_id=e.id, observation_id=o.observation.id).first()
            if eo is None:
                break
            else:
                db.session.delete(eo)
        db.session.commit()
        for l in e.locations:
            el = explanation_location.query.filter_by(explanation_id=e.id, location_id=l.location.id).first()
            if el is None:
                break
            else:
                db.session.delete(el)
        db.session.commit()
        db.session.delete(e)
        db.session.commit()
        return redirect('/all')


@app.route('/exname.json', methods=['GET', 'OPTIONS'])
@crossdomain(origin='*')
def exautocomplete():
    exs = explanation.query.all()
    results = [ex.name for ex in exs]
    return jsonify(results)


@app.route('/obname.json', methods=['GET', 'OPTIONS'])
@crossdomain(origin='*')
def obautocomplete():
    obs = observation.query.all()
    results = [ob.name for ob in obs]
    return jsonify(results)


@app.route('/new', methods=['GET', 'POST'])
def new_explanation():
    et = explanation_type.query.all()
    el = location.query.all()
    ob = observation.query.all()
    if request.method == 'POST':
        e = explanation(name=request.form['explanation'], typeid=request.form['typeid'])
        db.session.add(e)
        db.session.commit()
        e = explanation.query.filter_by(name=request.form['explanation']).first()
        for i in request.form.getlist('location'):
            nel = explanation_location(explanation_id=e.id, location_id=i)
            db.session.add(nel)
        db.session.commit()
        l = len(request.form) - 3
        l = int(l / 2)
        for i in range(l):
            print(i)
            s = 'os['+str(i)+'][observation]'
            w = 'os['+str(i)+'][wt]'
            if request.form[s] == "" or request.form[w] == "":
                continue
            oid = observation.query.filter_by(name=request.form[s]).first()
            if oid is None:
                o = observation(name=request.form[s])
                db.session.add(o)
                db.session.commit()
            o = observation.query.filter_by(name=request.form[s]).first()
            wt = float(request.form[w])
            neo = explanation_observation(explanation_id=e.id, observation_id=o.id, weight=wt)
            db.session.add(neo)
            db.session.commit()
        return redirect('/all')
    else:
        return render_template(
            'new.html',
            et=et,
            el=el,
            ob=ob,
            e=None
        )


@app.route('/newob', methods=['GET', 'POST'])
def new_observation():
    et = observation_type.query.all()
    if request.method == 'POST':
        ob = observation(name=request.form['observation'], typeid=request.form['typeid'])
        db.session.add(ob)
        db.session.commit()
        return redirect(url_for('allob'))
    else:
        return render_template('newob.html', et = et)


@app.route('/obdetail', methods=['GET', 'POST'])
def observation_detail():
    return

@app.route('/uo<int:observation_id>', methods=['GET', 'POST'])
@login_required
def update_observation(observation_id):
    e = observation.query.get(observation_id)
    et = observation_type.query.all()
    if request.method == 'GET':
        return render_template('updateob.html', et = et, e = e)
    else:
        e.name = request.form['observation']
        e.typeid = request.form['type']
        db.session.commit()
        return redirect(url_for('allob'))


