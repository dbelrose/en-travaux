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
-- Table structure for table `egw_sqlfs`
--

DROP TABLE IF EXISTS `egw_sqlfs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `egw_sqlfs` (
  `fs_id` int(11) NOT NULL AUTO_INCREMENT,
  `fs_dir` int(11) NOT NULL,
  `fs_name` varchar(200) NOT NULL,
  `fs_mode` smallint(6) NOT NULL,
  `fs_uid` int(11) NOT NULL DEFAULT '0',
  `fs_gid` int(11) NOT NULL DEFAULT '0',
  `fs_created` datetime NOT NULL,
  `fs_modified` datetime NOT NULL,
  `fs_mime` varchar(64) NOT NULL,
  `fs_size` bigint(20) NOT NULL,
  `fs_creator` int(11) NOT NULL,
  `fs_modifier` int(11) DEFAULT NULL,
  `fs_active` tinyint(4) NOT NULL DEFAULT '1',
  `fs_content` longblob,
  PRIMARY KEY (`fs_id`),
  KEY `egw_sqlfs_fs_dir_fs_active_fs_name` (`fs_dir`,`fs_active`,`fs_name`)
) ENGINE=MyISAM AUTO_INCREMENT=4480 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-08-07  7:59:50
