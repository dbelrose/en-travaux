-- MySQL dump 10.13  Distrib 8.0.31, for Win64 (x86_64)
--
-- Host: dbpnf.srv.gov.pf    Database: egroupware
-- ------------------------------------------------------
-- Server version	5.5.43-0+deb7u1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `egw_emailadmin`
--

DROP TABLE IF EXISTS `egw_emailadmin`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `egw_emailadmin` (
  `ea_profile_id` int(11) NOT NULL AUTO_INCREMENT,
  `ea_smtp_server` varchar(80) DEFAULT NULL,
  `ea_smtp_type` int(11) DEFAULT NULL,
  `ea_smtp_port` int(11) DEFAULT NULL,
  `ea_smtp_auth` char(3) DEFAULT NULL,
  `ea_editforwardingaddress` char(3) DEFAULT NULL,
  `ea_smtp_ldap_server` varchar(80) DEFAULT NULL,
  `ea_smtp_ldap_basedn` varchar(200) DEFAULT NULL,
  `ea_smtp_ldap_admindn` varchar(200) DEFAULT NULL,
  `ea_smtp_ldap_adminpw` varchar(30) DEFAULT NULL,
  `ea_smtp_ldap_use_default` char(3) DEFAULT NULL,
  `ea_imap_server` varchar(80) DEFAULT NULL,
  `ea_imap_type` int(11) DEFAULT NULL,
  `ea_imap_port` int(11) DEFAULT NULL,
  `ea_imap_login_type` varchar(20) DEFAULT NULL,
  `ea_imap_tsl_auth` char(3) DEFAULT NULL,
  `ea_imap_tsl_encryption` char(3) DEFAULT NULL,
  `ea_imap_enable_cyrus` char(3) DEFAULT NULL,
  `ea_imap_admin_user` varchar(40) DEFAULT NULL,
  `ea_imap_admin_pw` varchar(40) DEFAULT NULL,
  `ea_imap_enable_sieve` char(3) DEFAULT NULL,
  `ea_imap_sieve_server` varchar(80) DEFAULT NULL,
  `ea_imap_sieve_port` int(11) DEFAULT NULL,
  `ea_description` varchar(200) DEFAULT NULL,
  `ea_default_domain` varchar(100) DEFAULT NULL,
  `ea_organisation_name` varchar(100) DEFAULT NULL,
  `ea_user_defined_accounts` char(3) DEFAULT NULL,
  `ea_imapoldcclient` char(3) DEFAULT NULL,
  `ea_order` int(11) DEFAULT NULL,
  `ea_appname` varchar(80) DEFAULT NULL,
  `ea_group` varchar(80) DEFAULT NULL,
  `ea_smtp_auth_username` varchar(80) DEFAULT NULL,
  `ea_smtp_auth_password` varchar(80) DEFAULT NULL,
  `ea_user_defined_signatures` varchar(3) DEFAULT NULL,
  `ea_default_signature` text,
  `ea_user_defined_identities` varchar(3) DEFAULT NULL,
  `ea_user` varchar(80) DEFAULT NULL,
  `ea_active` int(11) DEFAULT NULL,
  `ea_imap_auth_username` varchar(80) DEFAULT NULL,
  `ea_imap_auth_password` varchar(80) DEFAULT NULL,
  PRIMARY KEY (`ea_profile_id`),
  KEY `egw_emailadmin_ea_appname` (`ea_appname`),
  KEY `egw_emailadmin_ea_group` (`ea_group`)
) ENGINE=MyISAM AUTO_INCREMENT=3 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-08-07  7:59:32
