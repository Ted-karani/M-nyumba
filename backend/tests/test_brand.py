# Import the files we are testing
import main
import twofactor


def test_the_product_is_called_estateloom():
    # The name of the API
    assert main.app.title == "EstateLoom"
    # The name shown in an authenticator app when 2-step login is set up
    assert "EstateLoom" in twofactor.otpauth_url("JBSWY3DPEHPK3PXP", "a@example.com")