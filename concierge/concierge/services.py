import urllib
from sqlalchemy.exc import IntegrityError
#from xml.etree.ElementTree import ParseError
from flask import Module, request, g, render_template, redirect, url_for
from flaskext.wtf import Form, TextField, IntegerField, BooleanField, \
                         Required, NumberRange, URL, ValidationError
from concierge import db
from concierge.auth import requires_auth
from concierge.services_models import Service
from concierge.service_metadata_parser import parse_metadata


services = Module(__name__, 'services')


class RegisterForm(Form):
    url = TextField('Metada URL', validators=[Required(), URL()])

    def validate_metadata_url(form, field):
        if Service.query.filter_by(url=form.metadata_url.data).first():
            raise ValidationError('This service is already registered')


class ServiceForm(Form):
    favorite = BooleanField('Favorite')
    rating = IntegerField('Rating', validators=[NumberRange(min=1, max=5)])


@services.route('/<id>', methods=['GET', 'POST'])
def service(id):
    user = getattr(g, 'user', None)
    service = Service.query.get_or_404(id)
    form = ServiceForm(request.form)

    if user:
        if form.validate_on_submit():
            if form.favorite.data and service not in user.favorite_services:
                user.favorite_services.append(service)
            elif not form.favorite.data and service in user.favorite_services:
                user.favorite_services.remove(service)
            user.rating_services[service] = form.rating.data
            db.session.commit()

            return redirect(url_for('service', id=id))

        form.favorite.data = service in user.favorite_services
        form.rating.data = user.rating_services.get(service)
    return render_template('service.html', service=service, form=form)


@services.route('/register', methods=['GET','POST'])
@requires_auth
def register():
    form = RegisterForm(request.form)
    if form.validate_on_submit():
        url = form.url.data
        try:
            metadata = urllib.urlopen(url).read()
            service = parse_metadata(metadata)
            service.metadata_url = url
            service.user = g.user
            db.session.add(service)
            db.session.commit()
            return redirect('/')
        except IOError:
            form.url.errors.append("Unable to fetch the metadata file")
        except ParseError:
            form.url.errors.append("Metadata file not well-formed")
        except IntegrityError:
            form.url.errors.append("Invalid metadata info, already registered ?")
            db.session.rollback()
    return render_template('register_service.html', form=form)


@services.route('/favorites')
def favorites():
    if hasattr(g, 'user'):
        user = g.user
        favorites = user.favorite_services
        return render_template('favorites.html',favorites=favorites)
    return render_template('favorites.html', favorites=[])


@services.route('/ratings')
def ratings():
    if hasattr(g, 'user'):
        user = g.user
        ratings = user.rating_services
        return render_template('ratings.html', ratings=ratings)
    return render_template('ratings.html', ratings={})


# /import?f=1&f=2&r=2.1
@services.route('/import')
@requires_auth
def imports():
    user = g.user
    favorites = set(request.args.getlist('f'))
    ratings = set([tuple(r.split('.')) for r in request.args.getlist('r')])

    for f in favorites:
        service = Service.query.get(f)
        if (service and service not in user.favorite_services):
            user.favorite_services.append(service)

    for r in ratings:
        service = Service.query.get(r[0])
        if (service):
            user.rating_services[service] = r[1]

    db.session.add(user)
    db.session.commit()
    return redirect("/")
