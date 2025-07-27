import {  Link  } from "react-router-dom";
import logoUrl from './assets/logo.png'; // adjust the path as needed

function Logo() {
  return <Link to="/"><img src={logoUrl} height="18" style={{margin: "2px 0 0 2px"}}></img></Link>
}
export default Logo;