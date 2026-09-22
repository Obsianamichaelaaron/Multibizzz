<?php
function getDBConnection() {

$servername = "localhost";
$username = "u190037990_multibiz";
$password = "multibizPass1";
$dbname = "u190037990_mb_db";

$conn = new mysqli($servername, $username, $password, $dbname);

if ($conn->connect_error) {
   die("Database Connection Error: " . $conn->connect_error);
}
return $conn;
}
?>