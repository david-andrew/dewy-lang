David Samson
530.646 Robot Devices, Kinematics, Dynamics, and Control
Lab 3 Submission

Before use:
Ensure that '/Lab3/helpers' is on the matlab path. The submission code calls several helper functions and variables from that directory. Additionally, make sure my Lab1 and Lab2 code are also on the path, and up to date.



To use this, simply run lab3.m while an instance of rvis is open with the ur5. Before running, make sure to hide the 'base_frame' and 'tool0' frames as they are not used and will make it harder to see. In this lab, I use 'base' as the spatial frame, and 'ee_link'as the tool frame.


Files and basic descriptions

.../Lab3 is the top level folder containing the entire lab

.../Lab3/lab3.m 		is the main matlab driver code

.../Lab3/ur5FwdKin.m		computes the forward kinematic map for the ur5

.../Lab3/ur5BodyJacobian.m 	computes the body jacobian of the ur5 (using the algorithm implemented in mathematica RobotLinks.m)

.../Lab3/manipulability.m 	computes the manipulability of the ur5 at a given configuration

.../Lab3/getXi.m 		extracts the associated twist coordinates from a homogeneous transformation matrix

.../Lab3/ur5RRcontrol.m		implements a resolved rate controller to control the ur5

.../Lab3/Report.pdf		is the lab report for this lab




.../Lab3/helpers contains a set of helper functions/scripts for performing the matlab operations

.../Lab3/helpers/e1.m			returns the x-unit vector [1 0 0]'

.../Lab3/helpers/e2.m			same as e1, except for y direction

.../Lab3/helpers/e3.m			same as e1, except for z direction

.../Lab3/helpers/epsilon		specifies numerical precision for comparing floating point values

.../Lab3/helpers/force_get_joints.m 	gets the current joints from the ur5

.../Lab3/helpers/hat.m			performs the hat operation on a vector in R^3

.../Lab3/helpers/prismatic_twist.m	computes the twist coordinates for a pure translation

.../Lab3/helpers/proj.m			projects a vector onto another vector

.../Lab3/helpers/revolute_twist.m	computes the twist coordinates for a pure rotation

.../Lab3/helpers/ur5Parameters.m	fills the current matlab workspace with important ur5 parameters such as the joint lengths and twist axes

.../Lab3/helpers/rigid_adjoint.m	computes the adjoint of a rigid transformation

.../Lab3/helpers/rigid_adjoint_inverse.m computes the inverse of the rigid adjoint

.../Lab3/helpers/ur5SpationJacobian	**Currently broken** implements the spatial jacobian algorithm outlined in the mathematica RobotLinks.m package

.../Lab3/helpers/vect.m			extracts the R^3 vector from a 3x3 skew symmetric matrix in so(3)

.../Lab3/helpers/vee.m			extracts the twist coordinates from a twist in se(3)

.../Lab3/helpers/wedge.m		packs twist coordinates into an se(3) matrix



.../Lab3/helpers/raw_report/...		contains work used to generate the report document



.../Lab3/helpers/html/...		contains the matlab output as an html document

