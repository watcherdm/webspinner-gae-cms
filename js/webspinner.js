(function(){
	var webspinner = nsjs.ns('webspinner');
	webspinner.ns('base');
	webspinner.base.load("WsModel", Backbone.Model.extend({
		sync : function(method, model){
			
		}
	}));
	webspinner.ns('ui');
	webspinner.ui.load('Modal', Backbone.View.extend({
		initialize : function(options){
			this.$el = $(this.el);
			this.$container = this.$('.container');
		},
		show : function(contents){
			this.$container.append(contents);
			this.$el.fadeIn();
		},
		hide : function(){
			this.$el.fadeOut();
			this.$container.empty();
		}
	}));

	// account management ajax pane
	webspinner.ns('account');
	webspinner.account.load("Status", Backbone.Model.extend({
		defaults : {
			loggedin : false
		},
		initialize : function(){
			this.fetch();
		},
		url : function(){
			return '/status';
		},
		parse : function(resp){
			if ( resp.loggedin && resp.user ){
				webspinner.account.user.set(resp.user);
			}
			return {
				loggedin : resp.loggedin
			}
		}
	}));
	webspinner.account.load("User", Backbone.Model.extend({
		action : function(){
			return this.isNew() ? 'add' : 'edit';
		},
		urlRoot : '/admin/',
		url : function(){
			return this.urlRoot + this.action() + '/user/' + this.id;
		},
		parse : function(response){
			
		}
	}));
	webspinner.account.load("Button", Backbone.View.extend({
		events : {
			'click' : 'on_click'
		},
		initialize : function(){
			this.model.bind('change:loggedin', this.render.bind(this));
		},
		on_click : function(){
			var toggle = this.model.get('loggedin');
			$.get(this.el.attr('href')).done($.proxy(function(resp){
				this.trigger('showform', resp);
			}, this));
			return false;
		},
		render : function(){
			var toggle = this.model.get('loggedin');
			this.el.text(toggle ? 'Account' : 'Login');
		}
	}));

	webspinner.bootstrap = function(){
		webspinner.account.status = new webspinner.account.Status();
		webspinner.account.user = new webspinner.account.User();
		webspinner.account.ns('controls');
		webspinner.account.controls.button = new webspinner.account.Button({
			el : $('.account.control'),
			model : webspinner.account.status
		});
		webspinner.account.controls.button.bind('showform', function(data){
			webspinner.ui.modal.show(data);
		});
		webspinner.ui.modal = new webspinner.ui.Modal({
			el : $('.overlay')
		});
	}
	$(webspinner.bootstrap);
})()