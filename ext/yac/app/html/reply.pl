use Mojolicious::Lite;

any '/arccn/post' => sub {
  my ($self) = @_;
  $self->app->log->debug($self->req->body);
  $self->render(text => 'ok');
};

app->start;

