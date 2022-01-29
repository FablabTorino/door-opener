<?php

error_reporting(E_ALL);
ini_set("display_errors", 1);

class WindDocTalker {
  private $url;
  private $soapclient;
  private $sessionId;
  private $token_app;
  private $token;

  function __construct($token, $token_app){
    $this->token = $token;
    $this->token_app = $token_app;
    $this->url = 'https://app.winddoc.com/v1/api.php?wsdl';
    $this->soapclient = new SoapClient(null,
                                        array('location' => $this->url,
                                        'uri'            => $this->url,
                                        'soap_version'   => SOAP_1_1,
                                        'trace'          => 1,
                                        'exceptions'     => 0
                                      ));
  }

  //******** Modifica Parametri Socio. Necessario id_socio
  /*$id_socio = "";
  $data = array();
  $data["campo1"] = "22";
  $ret = $WindDocTalker->ModificaSocio($id_socio, $data);*/
  public function ModificaSocio($id="1", $params = array()){
    if($this->Login()){
      $args = array(
        new SoapParam($this->sessionId,  'id_session'),
        new SoapParam($id,  'id'),
        new SoapParam($this->parseData($params),  'params'),
      );

      $ret = $this->__call("associazioni_soci_modifica", $args);
      $this->Close();
      return $ret;
    }
  }

  public function listaSoci($pagina="1", $query="", $length=10){
    if($this->Login()){
      $args = array(
        new SoapParam($this->sessionId,  'id_session'),
        new SoapParam($query,  'query'),
        new SoapParam($pagina,  'pagina'),
        new SoapParam("",  'order'),
        new SoapParam($length,  'length'),
      );

      $ret = $this->__call("associazioni_soci_listaCerca", $args);
      $this->Close();
      return $ret;
    }
  }

  public function parseData($data){
    $args = array();
    foreach ($data as $key => $value) {
      if(is_array($value)){
        $args[] = new SoapParam($this->parseData($value),  $key);
      }else{
        $args[] = new SoapParam($value,  $key);
      }
    }

    return $args;
  }

  public function Login(){
    $args = array(
      'token' => $this->token,
      'token_app' => $this->token_app
    );

    $this->sessionId = $this->__call("login", $args);
    if($this->sessionId!=""){
      return true;
    }
    return false;
  }

  public function Close(){
    $args = array(
    'id_session' => $this->sessionId
    );
    $this->__call("close", $args);
  }

  public function __call($method, $args){
    $response = $this->soapclient->__soapCall($method, $args);
    if(is_object($response) && get_class($response)=="SoapFault"){
      return array();
    }
    return $response;
  }
}

function arrayUserToObject($a) {
  $user = new stdClass();
  foreach ($a as $i) {
    $user->{$i->name} = $i->value;
  }
  return $user;
}

function extractInfo($user) {
  $res = new stdClass();
  $res->cardNumber = preg_match('/([A-Za-z]+[0-9]|[0-9]+[A-Za-z])[A-Za-z0-9]*/', $user->campo1) ? $user->campo1 : '';
  $res->fullName = $user->contatto_nome . ' ' . $user->contatto_cognome;
  $res->validUntil = property_exists($user, 'data_scadenza_rinnovo') ?
    strtotime($user->data_scadenza_rinnovo) : 0;
  if( $user->campo6 == '' | $user->campo6 == '1234') {
    $res->Pin = 'xxxx'; // H24
  }else{
    $res->Pin = $user->campo6;
  }
  if( $user->campo2 == '1') {
    $res->accessLevel = '99'; // H24
  }else{
    $res->accessLevel = '1'; // 16-20
  }
  return $res;
}

function isToSync($user) {
  return $user->cardNumber && $user->validUntil > time();
}

function loadEnv() {
  $envPath = dirname(__FILE__).'/.env';

  if (!is_readable($envPath)) {
    echo ".env file missing\n";
    exit;
  }

  $lines = file($envPath);
  foreach ($lines as $line) {
    if (strpos(trim($line), '#') === 0) {
      continue;
    }

    list($name, $value) = explode('=', $line, 2);
    $name = trim($name);
    $value = trim($value);

    if (!array_key_exists($name, $_ENV)) {
      $_ENV[$name] = $value;
    }
  }
}

function main() {
  loadEnv();

  $WindDocTalker = new WindDocTalker($_ENV['WINDDOC_TOKEN'], $_ENV['WINDDOC_TOKEN_APP']);
  
  $usersArr = $WindDocTalker->listaSoci(1, '', 1500);
  $users = array_map('arrayUserToObject', $usersArr->lista);
  $extractedInfo = array_map('extractInfo', $users);
  $usersToSync = array_values(array_filter($extractedInfo, 'isToSync'));
  
  $f = fopen(dirname(__FILE__).'/sync.json', 'w');
  fwrite($f, json_encode($usersToSync));
}

main();
