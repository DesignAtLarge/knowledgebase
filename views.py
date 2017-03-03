from flask import render_template, request, redirect, flash, url_for, session, jsonify
from models import explanation, observation, location, explanation_observation, explanation_type, explanation_location, User, db
from application import app, bcrypt, login_manager
from flask_login import login_user , logout_user , current_user , login_required
login_manager.login_view = 'login'


@login_manager.user_loader
def user_loader(user_id):
    return User.query.get(int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    if len(request.form) == 2:
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
        'diseases.html',
        all=explanation.query.all()
    )


@app.route('/', methods=["GET"])
@login_required
def index():
    return render_template(
        'index.html',
        a=explanation.query.count(),
        b=observation.query.count(),
        c=User.query.count(),
        d=location.query.count()
    )

@app.route('/s', methods=['GET', 'POST'])
@login_required
def search_explanation():
    e = explanation.query.filter(explanation.name.like('%' + str(request.form['query']) + '%')).all()
    if e is None:
        return redirect('/')
    else:
        return render_template(
            'diseases.html',
            all=e
        )


# @app.route('/new-disease', methods=['GET', 'POST'])
# def new_disease():
#     if request.method == 'POST':
#         d = disease(name=request.form['disease'])
#         db.session.add(d)
#         db.session.commit()
#         return redirect('/')
#     else:
#         return render_template(
#             'new-disease.html',
#             page='new-disease.html')
#


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
        for i in range(len(exobservations)):
            if exobservations[i] != e.observations[i].observation.name:
                dds = explanation_observation.query.filter_by(explanation_id=e.id, observation_id =e.observations[i].observation.id).first()
                db.session.delete(dds)
                db.session.commit()
                s = observation.query.filter_by(name=exobservations[i]).first()
                if s is None:
                    s = observation(name=request.form['observation'])
                    db.session.add(s)
                    db.session.commit()
                s = observation.query.filter_by(name=exobservations[i]).first()
                ds = explanation_observation(explanation_id=e.id, observation_id=s.id, weight=exweight[i])
                db.session.add(ds)
            else:
                s = observation.query.filter_by(name=exobservations[i]).first()
                ds = explanation_observation.query.filter_by(explanation_id=e.id, observation_id=s.id).first()
                ds.weight = exweight[i]
        db.session.commit()
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


@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    search = request.args.get('q')
    query = explanation.query.filter(explanation.name.like('%' + str(search) + '%'))
    results = [ex[1] for ex in query.all()]
    return jsonify(matching_results=results)

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
        l = len(request.form) - len(request.form.getlist('location')) - 2
        print (l)
        for i in range(0, l):
            s = 'os['+str(i)+'][observation]'
            w = 'os['+str(i)+'][wt]'
            oid = int(request.form[s])
            wt = float(request.form[w])
            neo = explanation_observation(explanation_id=e.id, observation_id=oid, weight=wt)
            db.session.add(neo)
        db.session.commit()
        return redirect('/all')
    else:
        return render_template(
            'new.html',
            et=et,
            el=el,
            ob=ob,
            e = None
        )